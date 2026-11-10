// Draws one frame of the rink scene in about half the time of a plain `gl.render(scene, camera)`.
//
// Why: the two end screens are clear plastic (glTF transmission). For a transmissive material three.js first draws
// every opaque object of the scene into an off-screen target (the picture seen through the plastic) and then draws the
// whole scene again on the canvas. On the CPU renderer (SwiftShader) that extra full-scene draw is half of a frame's
// time, and it produces the picture the canvas is about to hold anyway.
//
// How: the scene is drawn once, and the off-screen picture is made from that drawing.
//   1. the opaque objects, without the screens: one ordinary pass on the canvas (exactly the plain render's pixels);
//   2. the canvas' colour and depth are copied to textures;
//   3. a second render call draws only a full-screen quad, the screens and the transparent objects (the jersey prints).
//      three's own transmission code runs unchanged: it draws the "opaque objects" - now only the quad - into its
//      off-screen target. The quad writes the copied frame there, converted back from display values (ACES tone mapping,
//      sRGB) to the linear light the target holds in a plain render, and the copied depth. On the canvas the quad
//      draws nothing; the screens and then the prints are drawn by three as always, on top of step 1.
//
// What differs from the plain render: nothing outside the screens. Seen through a screen, the picture has passed
// through the canvas' 8 bits per channel (and highlights above display white are clipped), and the off-screen target
// gets one depth per pixel (the canvas' depth buffer, copied) where a plain render has one per sample, which shows on
// the pixels where a screen meets an opaque edge. Measured: docs/video-workflow.md section 8. `render(..., true)` (input prop `plainRender`) draws the plain single call, the reference.
//
// The plain call is also used when no screen is in view (three then makes no extra pass), and when the renderer is not
// set up as this file inverts it (ACES filmic tone mapping, sRGB output) or the canvas' depth cannot be copied.
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { getInputProps } from "remotion";
import * as THREE from "three";

type Drawable = THREE.Mesh & { material: THREE.Material };

export interface ScenePlan {
  mode: "plain" | "reuse";
  /** why the plain call was chosen, or what was drawn */
  reason: string;
}

/** Inverse of three's output for an opaque fragment: sRGB OETF after ACESFilmicToneMapping (tonemapping_pars_fragment). */
const FRAGMENT = /* glsl */ `
uniform sampler2D frame;
uniform sampler2D frameDepth;
uniform float exposure;
vec3 srgbToLinear( vec3 v ) {
  return mix( pow( ( v + 0.055 ) / 1.055, vec3( 2.4 ) ), v / 12.92, vec3( lessThanEqual( v, vec3( 0.04045 ) ) ) );
}
// y = ( v ( v + 0.0245786 ) - 0.000090537 ) / ( v ( 0.983729 v + 0.4329510 ) + 0.238081 ), solved for v >= 0
vec3 inverseRRTAndODTFit( vec3 y ) {
  vec3 qa = 0.983729 * y - 1.0;
  vec3 qb = 0.4329510 * y - 0.0245786;
  vec3 qc = 0.238081 * y + 0.000090537;
  return ( - qb - sqrt( max( qb * qb - 4.0 * qa * qc, 0.0 ) ) ) / ( 2.0 * qa );
}
vec3 inverseACESFilmic( vec3 color ) {
  // inverses of three's ACESInputMat and ACESOutputMat (tonemapping_pars_fragment), computed in double precision
  const mat3 ACESInputMatInverse = mat3( vec3( 1.764740972, -0.147027852, -0.036336830 ), vec3( -0.675777678, 1.160251512, -0.162436437 ), vec3( -0.088963294, -0.013223660, 1.198773267 ) );
  const mat3 ACESOutputMatInverse = mat3( vec3( 0.643038249, 0.059268690, 0.005961901 ), vec3( 0.311186752, 0.931436487, 0.063929016 ), vec3( 0.045775457, 0.009294916, 0.930118384 ) );
  color = ACESOutputMatInverse * color;
  color = inverseRRTAndODTFit( clamp( color, 0.0, 0.999 ) );
  color = ACESInputMatInverse * color;
  return max( color, 0.0 ) * 0.6 / exposure;
}
void main() {
  // the canvas' depth, so that the far side of a screen is hidden by what stands in front of it, as in a plain render
  gl_FragDepth = texelFetch( frameDepth, ivec2( gl_FragCoord.xy ), 0 ).r;
  vec4 t = texelFetch( frame, ivec2( gl_FragCoord.xy ), 0 );
  // nothing drawn here: keep the target's clear value (three clears it to white at half alpha)
  if ( t.a <= 0.0 ) discard;
  // an edge pixel is the mean of its covered samples (alpha 1) and its empty ones (colour 0, alpha 0); in the target
  // the empty samples hold the clear value, premultiplied: ( 0.5, 0.5, 0.5, 0.5 )
  vec3 linear = inverseACESFilmic( srgbToLinear( t.rgb / t.a ) );
  gl_FragColor = vec4( linear * t.a + 0.5 * ( 1.0 - t.a ), t.a + 0.5 * ( 1.0 - t.a ) );
}`;

/** Depth formats a canvas may have; the copy (a framebuffer blit) only succeeds into the same format. */
const DEPTH_FORMATS: { name: string; format: THREE.DepthTexturePixelFormat; type: THREE.TextureDataType }[] = [
  { name: "DEPTH24_STENCIL8", format: THREE.DepthStencilFormat, type: THREE.UnsignedInt248Type },
  { name: "DEPTH_COMPONENT24", format: THREE.DepthFormat, type: THREE.UnsignedIntType },
  { name: "DEPTH_COMPONENT16", format: THREE.DepthFormat, type: THREE.UnsignedShortType },
  { name: "DEPTH_COMPONENT32F", format: THREE.DepthFormat, type: THREE.FloatType },
];

export class SceneRenderer {
  private readonly gl: THREE.WebGLRenderer;
  private readonly drawables: Drawable[] = [];
  private readonly screens: Drawable[] = [];
  private readonly opaque: Drawable[] = [];
  private readonly later: Drawable[] = [];
  private readonly frustum = new THREE.Frustum();
  private readonly viewProjection = new THREE.Matrix4();
  private readonly size = new THREE.Vector2();
  private readonly quad: THREE.Mesh<THREE.BufferGeometry, THREE.ShaderMaterial>;
  private copy: THREE.FramebufferTexture | null = null;
  private depth: THREE.WebGLRenderTarget | null = null;
  /** index into DEPTH_FORMATS of the format the canvas' depth buffer has (found by trying), -1 = none could be copied */
  private depthFormat: number | null = null;

  constructor(gl: THREE.WebGLRenderer, root: THREE.Object3D) {
    this.gl = gl;
    root.traverse((o) => {
      const m = o as Drawable;
      if (!(m.isMesh || (o as THREE.Line).isLine || (o as THREE.Points).isPoints) || !m.geometry) return;
      if (Array.isArray(m.material)) throw new Error(`${o.name}: material arrays are not supported by the scene renderer`);
      this.drawables.push(m);
      const mat = m.material as THREE.MeshPhysicalMaterial;
      if (mat.transmission > 0) this.screens.push(m);
      else if (mat.transparent) this.later.push(m);
      else this.opaque.push(m);
    });
    // one triangle over the whole picture, in clip space (no camera); its only job is three's transmission target
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array([-1, -1, 0, 3, -1, 0, -1, 3, 0]), 3));
    const material = new THREE.ShaderMaterial({
      name: "frame_as_transmission_source",
      uniforms: { frame: { value: null }, frameDepth: { value: null }, exposure: { value: 1 } },
      vertexShader: "void main() { gl_Position = vec4( position.xy, 0.0, 1.0 ); }",
      fragmentShader: FRAGMENT,
      toneMapped: true,
    });
    this.quad = new THREE.Mesh(geometry, material);
    this.quad.name = "FrameQuad";
    this.quad.frustumCulled = false;
    // three draws the opaque list twice: into the transmission target (there the quad is the picture) and on the
    // canvas (there the picture is already drawn: every fragment of the quad is rejected before it is shaded)
    this.quad.onBeforeRender = (renderer) => {
      const onCanvas = renderer.getRenderTarget() === null;
      material.depthTest = true;  // GL writes depth only with the depth test on
      material.depthFunc = onCanvas ? THREE.NeverDepth : THREE.AlwaysDepth;
      material.depthWrite = !onCanvas;
      material.colorWrite = !onCanvas;
    };
  }

  /** Frees the GPU objects of the quad and the frame copy. */
  dispose(): void {
    this.quad.geometry.dispose();
    this.quad.material.dispose();
    this.copy?.dispose();
    this.depth?.depthTexture?.dispose();
    this.depth?.dispose();
  }

  /** Copies the canvas' depth buffer into a depth texture (resolving its samples). False when no format matches. */
  private copyDepth(w: number, h: number): boolean {
    const gl = this.gl;
    const g = gl.getContext() as WebGL2RenderingContext;
    const candidates = this.depthFormat === null ? DEPTH_FORMATS.map((_, i) => i) : this.depthFormat < 0 ? [] : [this.depthFormat];
    let ok = false;
    for (const i of candidates) {
      if (!this.depth || this.depth.width !== w || this.depth.height !== h || this.depthFormat === null) {
        this.depth?.depthTexture?.dispose();
        this.depth?.dispose();
        const f = DEPTH_FORMATS[i]!;
        const depthTexture = new THREE.DepthTexture(w, h, f.type, undefined, undefined, undefined, THREE.NearestFilter, THREE.NearestFilter, undefined, f.format);
        this.depth = new THREE.WebGLRenderTarget(w, h, { depthTexture, stencilBuffer: f.format === THREE.DepthStencilFormat, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
        gl.initRenderTarget(this.depth);
      }
      const framebuffer = (gl.properties.get(this.depth) as { __webglFramebuffer: WebGLFramebuffer }).__webglFramebuffer;
      while (g.getError() !== g.NO_ERROR) { /* errors of earlier calls are not this copy's */ }
      g.bindFramebuffer(g.READ_FRAMEBUFFER, null);
      g.bindFramebuffer(g.DRAW_FRAMEBUFFER, framebuffer);
      g.blitFramebuffer(0, 0, w, h, 0, 0, w, h, g.DEPTH_BUFFER_BIT, g.NEAREST);
      ok = g.getError() === g.NO_ERROR;
      g.bindFramebuffer(g.FRAMEBUFFER, null);
      if (ok) {
        if (this.depthFormat === null) console.log(`[scene-render] canvas depth copied as ${DEPTH_FORMATS[i]!.name}`);
        this.depthFormat = i;
        break;
      }
    }
    if (!ok) this.depthFormat = -1;
    // raw GL calls were made behind three's state cache
    gl.resetState();
    return ok;
  }

  /** Which way this scene and camera are drawn (depends on the matrices and the renderer set-up only). */
  plan(root: THREE.Object3D, camera: THREE.Camera): ScenePlan {
    const gl = this.gl;
    root.updateMatrixWorld();
    if (camera.parent === null) camera.updateMatrixWorld();
    camera.matrixWorldInverse.copy(camera.matrixWorld).invert();
    this.viewProjection.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.viewProjection);
    if (!this.screens.some((s) => s.visible && this.frustum.intersectsObject(s))) return { mode: "plain", reason: "no screen in view" };
    if (gl.toneMapping !== THREE.ACESFilmicToneMapping || gl.outputColorSpace !== THREE.SRGBColorSpace || gl.transmissionResolutionScale !== 1) return { mode: "plain", reason: "renderer output is not ACES filmic + sRGB at full transmission resolution" };
    if (gl.getRenderTarget() !== null) return { mode: "plain", reason: "not drawing on the canvas" };
    if (this.depthFormat === -1) return { mode: "plain", reason: "the canvas depth cannot be copied" };
    return { mode: "reuse", reason: "opaque pass, frame copy, screens and prints" };
  }

  /** Draws the frame. `forcePlain` gives the plain single call (the reference this renderer is checked against). */
  render(root: THREE.Scene, camera: THREE.Camera, forcePlain = false): ScenePlan {
    const gl = this.gl;
    const plan: ScenePlan = forcePlain ? { mode: "plain", reason: "plain render requested" } : this.plan(root, camera);
    if (plan.mode === "plain") {
      gl.render(root, camera);
      return plan;
    }
    const was = new Map(this.drawables.map((m) => [m, m.visible]));
    const only = (keep: Drawable[]): void => {
      for (const m of this.drawables) m.visible = false;
      for (const m of keep) m.visible = was.get(m)!;
    };
    const autoClear = gl.autoClear;
    try {
      only(this.opaque);
      gl.render(root, camera);
      gl.getDrawingBufferSize(this.size);
      if (!this.copy || this.copy.image.width !== this.size.x || this.copy.image.height !== this.size.y) {
        this.copy?.dispose();
        this.copy = new THREE.FramebufferTexture(this.size.x, this.size.y);
      }
      gl.copyFramebufferToTexture(this.copy);
      if (!this.copyDepth(this.size.x, this.size.y)) {
        // no depth to give the transmission target: finish this frame as the plain render (it redraws everything)
        for (const m of this.drawables) m.visible = was.get(m)!;
        gl.render(root, camera);
        return { mode: "plain", reason: "the canvas depth cannot be copied" };
      }
      this.quad.material.uniforms.frameDepth!.value = this.depth!.depthTexture;
      this.quad.material.uniforms.frame!.value = this.copy;
      this.quad.material.uniforms.exposure!.value = gl.toneMappingExposure;
      only([...this.screens, ...this.later]);
      root.add(this.quad);  // in the scene for this one call only
      gl.autoClear = false;
      gl.render(root, camera);
      return plan;
    } finally {
      this.quad.removeFromParent();
      for (const m of this.drawables) m.visible = was.get(m)!;
      gl.autoClear = autoClear;
    }
  }
}

/**
 * Makes this renderer the one that draws the canvas (R3F leaves the drawing to a `useFrame` callback with a priority).
 * The callback is only the place of the draw call: it runs once per `advance()` of the Remotion frame and uses nothing of
 * R3F's time arguments. Logs `[<logTag>-draw]` with the way the frame was drawn.
 */
export function useSceneDraw(scene: THREE.Object3D, logTag: string, frame: number): void {
  const { gl } = useThree();
  const renderer = useMemo(() => new SceneRenderer(gl, scene), [gl, scene]);
  useEffect(() => () => renderer.dispose(), [renderer]);
  const plain = (getInputProps() as { plainRender?: boolean }).plainRender === true;
  useFrame((three) => {
    const plan = renderer.render(three.scene, three.camera, plain);
    console.log(`[${logTag}-draw] ${JSON.stringify({ frame, mode: plan.mode, reason: plan.reason })}`);
  }, 1);
}
