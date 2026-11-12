// Combo editor AI helper (docs/combo-editor.md). Two ways, both without any server of ours:
//  1. "Any AI": the page writes a prompt (format guide + the current combination + the request) that the user pastes
//     into any chat AI, and reads the JSON answer back.
//  2. "Claude with your own key": the page calls the Claude API straight from the browser with the user's API key.
//     The key is kept in this browser's localStorage only and is sent to api.anthropic.com and nowhere else.
import { type Combo, formatGuide } from "./model.ts";

export const AI_MODELS = [
  { id: "claude-opus-5-5", label: "Claude Opus 5.5 (best)" },
  { id: "claude-sonnet-5-5", label: "Claude Sonnet 5.5 (cheaper)" },
  { id: "claude-haiku-5-5", label: "Claude Haiku 5.5 (cheapest)" },
] as const;

const INSTRUCTIONS = `You edit table hockey combination diagrams. You get the format, the current diagram as JSON and a request.
Answer with one or two plain sentences saying what you changed, then the COMPLETE updated diagram as one JSON object in a
\`\`\`json code block. Keep everything the request does not ask to change exactly as it is (same figure poses, same arrow
"id" values). Only use the fields of the format. Positions must be physically sensible: figures stay on their slots, the
puck lies beside a blade (not inside a figure) when a figure plays it, arrows start where the puck is.`;

export function buildPrompt(combo: Combo, request: string): { system: string; user: string } {
  const { camera: _camera, ...doc } = combo;
  return {
    system: `${INSTRUCTIONS}\n\n${formatGuide()}`,
    user: `Current diagram:\n\`\`\`json\n${JSON.stringify(doc)}\n\`\`\`\n\nRequest: ${request.trim() || "(describe the change you want here)"}`,
  };
}

/** The prompt as one text for pasting into any chat AI. */
export function promptForClipboard(combo: Combo, request: string): string {
  const p = buildPrompt(combo, request);
  return `${p.system}\n\n${p.user}`;
}

/** Finds the combo JSON in an AI answer (a fenced block, or the outermost braces) and the text around it. */
export function parseAnswer(text: string): { json: unknown; said: string } {
  const fences = [...text.matchAll(/```(?:json)?\s*([\s\S]*?)```/g)];
  const candidates = fences.map((m) => m[1]!).reverse();
  const a = text.indexOf("{"), b = text.lastIndexOf("}");
  if (a >= 0 && b > a) candidates.push(text.slice(a, b + 1));
  for (const c of candidates) {
    try {
      const json: unknown = JSON.parse(c);
      if (typeof json === "object" && json !== null) return { json, said: (fences.length ? text.slice(0, fences[0]!.index) : text.slice(0, a)).trim() };
    } catch { /* try the next candidate */ }
  }
  throw new Error("No JSON found in the answer. Ask the AI to reply with the complete diagram as one JSON object.");
}

/** Asks Claude with the user's own key. Streams, so a long answer cannot time out. */
export async function askClaude(opts: { apiKey: string; model: string; combo: Combo; request: string; onText: (soFar: string) => void; signal: AbortSignal }): Promise<string> {
  const { default: Anthropic } = await import("@anthropic-ai/sdk");
  const client = new Anthropic({ apiKey: opts.apiKey, dangerouslyAllowBrowser: true });
  const p = buildPrompt(opts.combo, opts.request);
  try {
    const stream = client.beta.messages.stream(
      {
        model: opts.model,
        max_tokens: 32000,
        thinking: { type: "adaptive" },
        output_config: { effort: "medium" },
        // if the model declines, the API reruns the request on a fallback model inside the same call
        betas: ["server-side-fallback-2026-07-01"],
        fallbacks: "default",
        system: p.system,
        messages: [{ role: "user", content: p.user }],
      },
      { signal: opts.signal },
    );
    let text = "";
    stream.on("text", (delta) => { text += delta; opts.onText(text); });
    const message = await stream.finalMessage();
    if (message.stop_reason === "refusal") throw new Error("Claude declined this request.");
    if (message.stop_reason === "max_tokens") throw new Error("The answer was cut off before it finished. Try a simpler request.");
    return message.content.flatMap((b) => (b.type === "text" ? [b.text] : [])).join("");
  } catch (e) {
    if (e instanceof Anthropic.AuthenticationError) throw new Error("The API key was not accepted. Check it at console.anthropic.com.");
    if (e instanceof Anthropic.PermissionDeniedError) throw new Error("This API key may not use that model.");
    if (e instanceof Anthropic.RateLimitError) throw new Error("Rate limit reached. Wait a moment and try again.");
    if (e instanceof Anthropic.BadRequestError) throw new Error(`Claude could not take the request: ${e.message}`);
    if (e instanceof Anthropic.APIConnectionError) throw new Error("Could not reach the Claude API. Check your connection.");
    if (e instanceof Anthropic.APIError) throw new Error(`Claude API error ${e.status ?? ""}: ${e.message}`);
    throw e;
  }
}
