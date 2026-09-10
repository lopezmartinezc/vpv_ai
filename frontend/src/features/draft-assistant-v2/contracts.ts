import { z } from "zod";

export const positionSchema = z.enum(["POR", "DEF", "MED", "DEL"]);
export const contextSchema = z.object({
  selected_player_ids: z.array(z.number().int().positive()).max(3),
  participant_id: z.number().int().positive().nullable(),
  position: positionSchema.nullable(),
  team: z.string().max(100), search: z.string().max(100),
  order: z.enum(["priority", "vorp", "gain"]),
});
export const revisionSchema = z.object({
  draft: z.string(), board: z.string(), at: z.string(), pick_count: z.number(),
});
export const cardSchema = z.object({
  player_id: z.number().int(), name: z.string(), position: z.string(), team: z.string(),
  available: z.boolean(), priority: z.number().nullable(), priority_base: z.number().nullable(),
  vorp: z.number().nullable(), participation: z.number().nullable(),
  available_gap: z.number().nullable(), marginal_gain: z.number().nullable(), tags: z.array(z.string()), evidence_id: z.string(),
});
export const answerSchema = z.object({
  text: z.string(), cards: z.array(cardSchema), evidence_ids: z.array(z.string()),
  status: z.enum(["current", "stale", "incomplete"]), warnings: z.array(z.string()),
  revision: revisionSchema, provider: z.string(), model: z.string(),
  usage: z.object({input_tokens: z.number(), output_tokens: z.number(), rounds: z.number(),
    tool_calls: z.number(), latency_ms: z.number()}),
});
export const historySchema = z.object({
  exchanges: z.array(z.object({question: z.string(), answer: answerSchema})),
});
export const capabilitiesSchema = z.object({
  enabled: z.boolean(), default: z.string(),
  providers: z.array(z.object({name: z.enum(["openai", "anthropic"]),
    models: z.array(z.string()), default_model: z.string()})),
});
export const askSchema = z.object({
  question: z.string().trim().min(1).max(4000),
  provider: z.enum(["openai", "anthropic"]), model: z.string().min(1).max(100),
  participation: z.enum(["mixto", "historico"]), mode: z.enum(["quick", "detailed"]),
  context: contextSchema,
});
export type Answer = z.infer<typeof answerSchema>;
export type Card = z.infer<typeof cardSchema>;
export type Revision = z.infer<typeof revisionSchema>;
export type History = z.infer<typeof historySchema>;
export type Capabilities = z.infer<typeof capabilitiesSchema>;
export type Ask = z.infer<typeof askSchema>;
export type ViewContext = z.infer<typeof contextSchema>;

export interface PanelProps {
  draftId: number;
  active: boolean;
  liveToken: string;
  context: ViewContext;
  participants: {participant_id: number; display_name: string}[];
  players: {player_id: number; display_name: string}[];
  onSelect: (id: number) => void;
}
