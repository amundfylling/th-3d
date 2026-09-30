// Post-import checks (iteration 19): the imported GLB must agree with the canonical pose data converted
// once by the project adapter. Runs in the browser during the Remotion render; results are logged.
import * as THREE from "three";
import geometry from "../data/geometry.json" with { type: "json" };
import poses from "../validation/16-assembly-poses.json" with { type: "json" };
import { worldMmToGltfM } from "../src/model/coordinates.ts";
import { transformPoint, type Mat4, type Vec3 } from "../src/model/pose.ts";

export interface ImportCheck {
  name: string;
  pass: boolean;
  detail: string;
}

/** GLTFLoader sanitises node names (removes '.', ':' etc.), so match on the sanitised form. */
const find = (root: THREE.Object3D, name: string): THREE.Object3D | undefined =>
  root.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(name));

export function runImportChecks(root: THREE.Object3D): ImportCheck[] {
  root.updateMatrixWorld(true);
  const checks: ImportCheck[] = [];
  const figure = poses.figures.find((f) => f.player_id === "W-RD")!;
  const node = find(root, "Figure.W-RD");
  if (!node) return [{ name: "Figure.W-RD present", pass: false, detail: "node not found" }];

  // 1. Known basis point: W-RD fixture axis (pose functions, mm, z up) -> adapter -> three (m, Y up).
  const expected = new THREE.Vector3(...worldMmToGltfM(figure.pivot_mm as Vec3));
  const actual = new THREE.Vector3().setFromMatrixPosition(node.matrixWorld);
  const dPivot = expected.distanceTo(actual) * 1000;
  checks.push({ name: "basis point: W-RD fixture axis", pass: dPivot < 0.01, detail: `expected ${expected.toArray().map((v) => v.toFixed(5))} m, got ${actual.toArray().map((v) => v.toFixed(5))} m, diff ${dPivot.toFixed(4)} mm` });

  // 2. Blade orientation: the stored W-RD blade (pivot-local mm) placed by the pose matrix, vs the same
  // local points carried by the imported node's world matrix.
  const blade = geometry.figure_assets.find((a) => a.id === "fig.W-RD")!.contact_shapes.find((c) => c.kind === "blade")!.geometry!.points_mm as Vec3[];
  const [b0, b1] = [blade[0]!, blade[1]!];
  const viaPose = [b0, b1].map((p) => new THREE.Vector3(...worldMmToGltfM(transformPoint(figure.matrix as unknown as Mat4, p))));
  const viaImport = [b0, b1].map((p) => new THREE.Vector3(...worldMmToGltfM(p)).applyMatrix4(node.matrixWorld));
  const dirPose = viaPose[1]!.clone().sub(viaPose[0]!).normalize();
  const dirImport = viaImport[1]!.clone().sub(viaImport[0]!).normalize();
  const angle = THREE.MathUtils.radToDeg(dirPose.angleTo(dirImport));
  const dTip = viaPose[1]!.distanceTo(viaImport[1]!) * 1000;
  // Handedness: the blade tip must lie on the figure's left, i.e. +Y_local x heading points up (+Y three).
  const heading = new THREE.Vector3(...worldMmToGltfM([1, 0, 0])).applyMatrix3(new THREE.Matrix3().setFromMatrix4(node.matrixWorld)).normalize();
  const toTip = viaImport[1]!.clone().sub(actual).setY(0).normalize();
  const leftSide = new THREE.Vector3().crossVectors(heading, toTip).y > 0;
  checks.push({ name: "blade orientation: W-RD blade direction and tip", pass: angle < 0.01 && dTip < 0.01 && leftSide, detail: `direction diff ${angle.toFixed(5)} deg, tip diff ${dTip.toFixed(4)} mm, blade on figure's left: ${leftSide}` });

  // 3. Units and axes: the imported ice extent equals the canonical boundary converted once.
  const ice = find(root, "Ice");
  if (ice) {
    const box = new THREE.Box3().setFromObject(ice);
    const pts = geometry.board.inner_boundary.world!.points_mm as [number, number][];
    const lenM = (Math.max(...pts.map((p) => p[0])) - Math.min(...pts.map((p) => p[0]))) / 1000;
    const widM = (Math.max(...pts.map((p) => p[1])) - Math.min(...pts.map((p) => p[1]))) / 1000;
    const dx = Math.abs(box.max.x - box.min.x - lenM) * 1000, dz = Math.abs(box.max.z - box.min.z - widM) * 1000;
    checks.push({ name: "units/axes: ice extent (x = length, z = width, m)", pass: dx < 0.1 && dz < 0.1 && Math.abs(box.max.y) < 1e-6, detail: `length diff ${dx.toFixed(4)} mm, width diff ${dz.toFixed(4)} mm, ice top Y ${box.max.y.toFixed(6)} m` });
  }
  return checks;
}
