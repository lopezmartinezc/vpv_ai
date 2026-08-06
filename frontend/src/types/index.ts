export interface PlayerPrediction {
  player_id: number;
  player_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  opponent_name: string;
  is_home: boolean;
  season_avg: number;
  form_5: number | null;
  location_avg: number | null;
  rival_factor: number;
  xpts: number;
  xpts_floor: number;
  xpts_ceiling: number;
  confidence: string;
  trend: string;
  matchdays_played: number;
  starter_pct: number;
  is_penalty_taker: boolean;
}

export interface OpponentDifficulty {
  team_name: string;
  goals_conceded_avg: number;
  clean_sheet_pct: number;
  difficulty: string;
}

export interface PredictionsResponse {
  season_id: number;
  matchday_number: number;
  predictions: PlayerPrediction[];
  opponent_rankings: OpponentDifficulty[];
}

export interface PlayerDraftStats {
  player_id: number;

  // Model output (Ensemble, Spearman 0.718 backtested)
  ensemble_score: number;
  signal: "strong_buy" | "buy" | "hold" | "avoid" | string;
  signal_reasons: string[];

  // Scorecard heuristics (docs/DRAFT_SCORECARD.md)
  position_tier: "elite" | "solid" | "normal" | "weak" | "team_dependent" | string;
  survival_haircut_pct: number; // 0..1
  effective_score: number; // ensemble_score * (1 - haircut)
  is_mover: boolean;
  is_peak_year: boolean;
  is_likely_penalty_taker: boolean;
  is_bench_risk: boolean; // Step 0: starter_pct < 0.79 OR games < 22
  mover_penalty_hint: number | null; // pts hint shown when is_mover (POR 2.0, others 1.0)

  // Supporting numbers shown in the card
  avg_pts: number;
  matchdays_played: number;
  starter_pct: number;
}

export interface DraftPlayerStatsResponse {
  players: Record<string, PlayerDraftStats>;
  suggestions: Record<string, number[]>;
}

export interface HealthCheck {
  status: string;
  database: boolean;
  version: string;
}

export interface AchievementEntry {
  id: number;
  achievement_key: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  tier: number;
  participant_id: number;
  display_name: string;
  matchday_number: number | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface SeasonAchievementsResponse {
  season_id: number;
  achievements: AchievementEntry[];
}

export interface SeasonSummary {
  id: number;
  name: string;
  status: string;
  matchday_current: number;
  matchday_end?: number | null;
  total_participants: number;
  lineup_deadline_min: number;
  kind?: "league" | "tournament";
  tournament_type?: string | null;
  /**
   * False ⇒ hide /economia + Pagometro widgets + nav cards. Typical
   * for torneos cortos that don't run the weekly-payments mechanic.
   * Treat undefined as true (back-compat with older bundles).
   */
  weekly_payments_enabled?: boolean;
}

export interface SeasonDetail {
  id: number;
  name: string;
  status: string;
  matchday_start: number;
  matchday_end: number | null;
  matchday_current: number;
  matchday_winter: number | null;
  matchday_scanned: number;
  draft_pool_size: number;
  lineup_deadline_min: number;
  total_participants: number;
  created_at: string;
}

export interface ScoringRule {
  id: number;
  rule_key: string;
  position: string | null;
  value: string;
  description: string | null;
}

export interface ValidFormation {
  id: number;
  formation: string;
  defenders: number;
  midfielders: number;
  forwards: number;
}

export interface StandingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  total_points: number;
  matchdays_played: number;
  avg_points: number;
}

export interface StandingsResponse {
  season_id: number;
  season_name: string;
  entries: StandingEntry[];
}

export interface MatchdaySummaryItem {
  number: number;
  status: string;
  counts: boolean;
  stats_ok: boolean;
  first_match_at: string | null;
}

export interface MatchdayListResponse {
  season_id: number;
  matchdays: MatchdaySummaryItem[];
}

export interface MatchEntry {
  id: number;
  home_team: string;
  away_team: string;
  home_team_id: number;
  away_team_id: number;
  home_score: number | null;
  away_score: number | null;
  counts: boolean;
  played_at: string | null;
  /** Knockout penalty-shootout winner (bracket progression only). */
  ko_winner_team_id?: number | null;
}

export interface ParticipantScore {
  rank: number | null;
  participant_id: number;
  display_name: string;
  total_points: number;
  formation: string | null;
  pending_players: number;
}

export interface HighlightPlayer {
  player_id: number;
  player_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  points: number;
  owner_name: string;
  goals: number;
  assists: number;
}

export interface DreamTeamPlayer {
  player_id: number;
  player_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  points: number;
}

export interface DreamTeamResponse {
  formation: string;
  total_points: number;
  players: DreamTeamPlayer[];
}

export interface MatchdayHighlightsResponse {
  matchday_number: number;
  mvp: HighlightPlayer | null;
  flop: HighlightPlayer | null;
  top_scorer: HighlightPlayer | null;
  top_assister: HighlightPlayer | null;
  dream_team: DreamTeamResponse | null;
  nightmare_team: DreamTeamResponse | null;
}

export interface MatchdayDetailResponse {
  season_id: number;
  number: number;
  status: string;
  counts: boolean;
  stats_ok: boolean;
  first_match_at: string | null;
  matches: MatchEntry[];
  scores: ParticipantScore[];
}

export interface ScoreBreakdown {
  pts_play: number;
  pts_starter: number;
  pts_result: number;
  pts_clean_sheet: number;
  pts_goals: number;
  pts_penalty_goals: number;
  pts_assists: number;
  pts_penalties_saved: number;
  pts_woodwork: number;
  pts_penalties_won: number;
  pts_penalties_missed: number;
  pts_own_goals: number;
  pts_yellow: number;
  pts_red: number;
  pts_pen_committed: number;
  pts_marca: number;
  pts_as: number;
  pts_total: number;
}

export interface LineupPlayerEntry {
  display_order: number;
  position_slot: string;
  player_id: number;
  player_name: string;
  photo_path: string | null;
  team_name: string;
  points: number;
  score_breakdown: ScoreBreakdown | null;
}

export interface BenchPlayerEntry {
  player_id: number;
  player_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  matchday_points: number;
  score_breakdown: ScoreBreakdown | null;
}

export interface LineupDetailResponse {
  participant_id: number;
  display_name: string;
  matchday_number: number;
  formation: string;
  total_points: number;
  players: LineupPlayerEntry[];
  bench: BenchPlayerEntry[];
}

export interface PositionCounts {
  POR: number;
  DEF: number;
  MED: number;
  DEL: number;
}

export interface SquadSummary {
  participant_id: number;
  display_name: string;
  total_players: number;
  season_points: number;
  positions: PositionCounts;
}

export interface SquadListResponse {
  season_id: number;
  squads: SquadSummary[];
}

export interface FormMatch {
  played: boolean;
  result: number; // 0=L, 1=D, 2=W
  is_home: boolean;
  points: number;
}

export interface PlayerRecentForm {
  matches: FormMatch[];
  clean_sheets: number;
  goals: number;
  assists: number;
  penalty_goals: number;
  yellow_cards: number;
}

export interface SquadPlayerEntry {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  season_points: number;
  recent_form: PlayerRecentForm | null;
  /** Opponent team name for the matchday being submitted. Null when the
   *  player's team has no scheduled match in this matchday. */
  opponent_team_name?: string | null;
  /** True if the player's team plays at home in this matchday. */
  is_home?: boolean | null;
}

export interface SquadDetailResponse {
  participant_id: number;
  display_name: string;
  season_points: number;
  players: SquadPlayerEntry[];
}

// Drafts
export interface DraftSummary {
  id: number;
  phase: string;
  draft_type: string;
  status: string;
  total_picks: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface DraftListResponse {
  season_id: number;
  drafts: DraftSummary[];
}

export interface DraftParticipant {
  participant_id: number;
  user_id: number;
  display_name: string;
  draft_order: number | null;
}

export interface DraftPickEntry {
  id: number;
  pick_number: number;
  round_number: number;
  participant_id: number;
  display_name: string;
  draft_order: number | null;
  player_id: number;
  player_name: string;
  position: string;
  team_name: string;
  photo_path: string | null;
  dropped_player_name: string | null;
  origin?: "manual" | "auto";
}

export interface DraftDetailResponse {
  id: number;
  season_id: number;
  phase: string;
  draft_type: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  participants: DraftParticipant[];
  picks: DraftPickEntry[];
  next_participant_id: number | null;
}

// Draft management
export interface CreateDraftResponse {
  id: number;
  season_id: number;
  phase: string;
  draft_type: string;
  status: string;
}

export interface AddPickResponse {
  pick_number: number;
  round_number: number;
  participant_id: number;
  display_name: string;
  player_id?: number;
  player_name: string;
  position: string;
  team_name: string;
  photo_path?: string | null;
  origin?: "manual" | "auto";
}

// Draft auto-pick wishlist
export interface WishlistPlayerItem {
  player_id: number;
  display_name: string;
  position: string | null;
  team_name: string | null;
  photo_path: string | null;
  is_already_picked: boolean;
  priority: number;
}

export interface Wishlist {
  draft_id: number;
  participant_id: number;
  enabled: boolean;
  players: WishlistPlayerItem[];
}

export interface AdminWishlist {
  participant_id: number;
  display_name: string;
  enabled: boolean;
  total: number;
}

// ---------------------------------------------------------------------------
// Playoff competitions
// ---------------------------------------------------------------------------

export interface FormatInfo {
  format_id: string;
  display_name: string;
  n_rounds_regular: number;
  n_rounds_ko: number;
}

export interface CompetitionDetail {
  id: number;
  season_id: number;
  name: string;
  type: string;
  status: "pending" | "regular" | "ko" | "completed" | string;
  config: Record<string, unknown> | null;
}

export interface CompetitionSummary {
  id: number;
  season_id: number;
  name: string;
  type: string;
  status: string;
}

export interface CompetitionListResponse {
  season_id: number;
  competitions: CompetitionSummary[];
}

export interface MatchupEntry {
  id: number;
  phase: "regular" | "ko" | string;
  group_label: string | null;
  round_label: string | null;
  round_number: number;
  matchday_id: number | null;
  matchday_number: number | null;
  participant_a_id: number | null;
  participant_a_name: string | null;
  participant_b_id: number | null;
  participant_b_name: string | null;
  feeder_a_id: number | null;
  feeder_b_id: number | null;
  score_a: number | null;
  score_b: number | null;
  winner_participant_id: number | null;
  winner_name: string | null;
}

export interface CompetitionMatchupsResponse {
  competition: CompetitionDetail;
  matchups: MatchupEntry[];
}

export interface StandingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  group_label: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  rests: number;
  points: number;
  diff_avg: number;
  pts_total_vpv: number;
}

export interface GroupStandings {
  label: string;
  entries: StandingEntry[];
}

export interface CompetitionStandingsResponse {
  competition: CompetitionDetail;
  groups: GroupStandings[];
}

export interface PlayerSearchItem {
  id: number;
  display_name: string;
  position: string;
  team_name: string;
  photo_path: string | null;
  is_already_picked: boolean;
}

export interface DraftTeamOption {
  id: number;
  name: string;
}

export interface PlayerSearchResponse {
  players: PlayerSearchItem[];
}

// Economy
export interface ParticipantBalance {
  participant_id: number;
  display_name: string;
  initial_fee: number;
  weekly_total: number;
  draft_fees: number;
  net_balance: number;
}

export interface EconomyResponse {
  season_id: number;
  balances: ParticipantBalance[];
}

export interface TransactionEntry {
  id: number;
  type: string;
  amount: number;
  description: string | null;
  matchday_number: number | null;
  created_at: string;
}

export interface ParticipantEconomyResponse {
  participant_id: number;
  display_name: string;
  net_balance: number;
  transactions: TransactionEntry[];
}

// Lineup submission ("my lineup" endpoint)
export interface LineupPlayerResponseData {
  player_id: number;
  player_name: string;
  position_slot: string;
  display_order: number;
  photo_path: string | null;
}

export interface CurrentLineupData {
  lineup_id: number;
  formation: string;
  confirmed: boolean;
  confirmed_at: string | null;
  telegram_sent: boolean;
  players: LineupPlayerResponseData[];
}

export interface LineupHistoryPlayerEntry {
  player_id: number;
  player_name: string;
  position_slot: string;
  display_order: number;
  photo_path: string | null;
  points: number;
}

export interface LineupHistoryEntry {
  matchday_number: number;
  formation: string;
  total_points: number;
  confirmed_at: string | null;
  players: LineupHistoryPlayerEntry[];
}

export interface MissedCall {
  position: string;
  benched_name: string;
  benched_points: number;
  benched_position?: string;
  lined_up_name: string;
  lined_up_points: number;
  lined_up_position?: string;
}

export interface MatchdayAccuracy {
  matchday_number: number;
  actual_points: number;
  optimal_points: number;
  accuracy_pct: number;
  formation_used: string;
  optimal_formation: string;
  missed_calls: MissedCall[];
}

export interface AccuracyResponse {
  participant_id: number;
  display_name: string;
  season_name: string;
  avg_accuracy: number;
  perfect_weeks: number;
  total_missed_points: number;
  matchdays: MatchdayAccuracy[];
}

export interface AccuracyRankingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  avg_accuracy: number;
  perfect_weeks: number;
  total_missed_points: number;
  matchdays_played: number;
}

export interface AccuracyPlayerEntry {
  player_id: number;
  name: string;
  position: string;
  points: number;
  in_optimal: boolean;
  in_actual: boolean;
}

export interface AccuracyMatchdayRankingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  actual_points: number;
  optimal_points: number;
  accuracy_pct: number;
  formation_used: string;
  optimal_formation: string;
  players: AccuracyPlayerEntry[];
  missed_calls: MissedCall[];
}

export interface AccuracyRankingResponse {
  season_id: number;
  season_name: string;
  matchday_number: number | null;
  entries: AccuracyRankingEntry[];
  matchday_entries: AccuracyMatchdayRankingEntry[] | null;
}

export interface LineupHistoryResponse {
  participant_id: number;
  display_name: string;
  season_name: string;
  lineups: LineupHistoryEntry[];
}

export interface MyLineupResponse {
  participant_id: number;
  display_name: string;
  lineup_deadline_min: number;
  current_lineup: CurrentLineupData | null;
  squad: SquadPlayerEntry[];
}

// Copa
export interface CopaMatchdayResult {
  participant_id: number;
  display_name: string;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
}

export interface CopaMatchdayDetail {
  matchday_number: number;
  results: CopaMatchdayResult[];
}

export interface CopaStandingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  total_points: number;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  total_goals_for: number;
  total_goals_against: number;
  goal_difference: number;
}

export interface CopaFullResponse {
  season_id: number;
  season_name: string;
  standings: CopaStandingEntry[];
  matchdays: CopaMatchdayDetail[];
}

// Dashboard (combined endpoint)
export interface DashboardResponse {
  standings: StandingsResponse | null;
  current_matchday: MatchdayDetailResponse | null;
  copa: CopaFullResponse | null;
  economy: EconomyResponse | null;
}

// ---------------------------------------------------------------------------
// Stats (admin) — matches backend/src/features/stats/schemas.py
// ---------------------------------------------------------------------------

export interface PlayerStatRow {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  goals: number;
  penalty_goals: number;
  own_goals: number;
  assists: number;
  penalties_saved: number;
  yellow_cards: number;
  red_cards: number;
  avg_marca: number | null;
  avg_as: number | null;
  minutes_played: number;
  matchdays_played: number;
  started_count: number;
  avg_points: number;
  total_points: number;
}

export interface PlayerStatsResponse {
  season_id: number;
  players: PlayerStatRow[];
}

export interface ParticipantBreakdown {
  participant_id: number;
  display_name: string;
  pts_play: number;
  pts_result: number;
  pts_clean_sheet: number;
  pts_goals: number;
  pts_assists: number;
  pts_yellow: number;
  pts_red: number;
  pts_marca_as: number;
  pts_total: number;
}

export interface ParticipantExtremes {
  participant_id: number;
  display_name: string;
  best_points: number;
  best_matchday: number;
  worst_points: number;
  worst_matchday: number;
  avg_points: number;
}

export interface EvolutionEntry {
  matchday_number: number;
  participant_id: number;
  display_name: string;
  points: number;
  cumulative: number;
}

export interface ParticipantStatsResponse {
  season_id: number;
  breakdowns: ParticipantBreakdown[];
  extremes: ParticipantExtremes[];
  evolution: EvolutionEntry[];
}

export interface FormationUsage {
  formation: string;
  usage_count: number;
}

export interface MostLinedUpPlayer {
  player_id: number;
  display_name: string;
  position: string;
  team_name: string;
  photo_path: string | null;
  times_lined_up: number;
}

export interface MatchdayAverageEntry {
  matchday_number: number;
  avg_points: number;
  max_points: number;
  min_points: number;
}

export interface RecordEntry {
  label: string;
  value: string;
  detail: string;
}

export interface LeagueStatsResponse {
  season_id: number;
  formations: FormationUsage[];
  most_lined_up: MostLinedUpPlayer[];
  matchday_averages: MatchdayAverageEntry[];
  records: RecordEntry[];
}

// Advanced stats (admin) — matches backend/src/features/stats/schemas_advanced.py

export interface AdvancedPlayerStat {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  matchdays_played: number;
  minutes_played: number;
  total_points: number;
  avg_points: number;
  std_dev: number;
  cv: number;
  p10: number;
  p50: number;
  p90: number;
  pp90: number;
  ci_lower: number;
  ci_upper: number;
  form_5: number | null;
  trend: "rising" | "stable" | "falling";
}

export interface AdvancedPlayersResponse {
  season_id: number;
  players: AdvancedPlayerStat[];
}

// Position value analysis (Phase 2)

export interface PositionTierPlayer {
  player_id: number;
  display_name: string;
  team_name: string;
  total_points: number;
  par: number;
}

export interface PositionTier {
  tier: number;
  label: string;
  min_points: number;
  max_points: number;
  players: PositionTierPlayer[];
}

export interface PositionAnalysis {
  position: string;
  player_count: number;
  replacement_level: number;
  avg_points: number;
  median_points: number;
  scarcity_index: number;
  tiers: PositionTier[];
}

export interface PositionValueResponse {
  season_id: number;
  positions: PositionAnalysis[];
}

// Draft history (Phase 3)

export interface PickValuePoint {
  pick_number: number;
  avg_total_points: number;
  sample_count: number;
}

export interface PositionRoundValue {
  round_number: number;
  position: string;
  avg_total_points: number;
  pick_count: number;
}

export interface RateEntry {
  round_range: string;
  rate_pct: number;
  total_picks: number;
}

export interface DraftHistoryResponse {
  pick_value_curve: PickValuePoint[];
  position_by_round: PositionRoundValue[];
  bust_rate: RateEntry[];
  steal_rate: RateEntry[];
}

// Context analysis (Phase 4)

export interface PlayerSplit {
  location: "home" | "away";
  matches: number;
  avg_points: number;
  total_points: number;
  goals: number;
  assists: number;
}

export interface PlayerSplitsResponse {
  player_id: number;
  display_name: string;
  season_id: number;
  splits: PlayerSplit[];
}

export interface TeamDependencyEntry {
  team_name: string;
  top_player_name: string;
  top_player_id: number;
  top_player_points: number;
  team_total_points: number;
  dependency_pct: number;
}

export interface TeamDependencyResponse {
  season_id: number;
  entries: TeamDependencyEntry[];
}

export interface ComparePlayerAxis {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  goals_rate: number;
  assists_rate: number;
  avg_points: number;
  consistency: number;
  pp90: number;
  form: number;
}

export interface ComparePlayersResponse {
  season_id: number;
  players: ComparePlayerAxis[];
}

// Palmares

export interface PodiumEntry {
  rank: number;
  user_id: number;
  display_name: string;
  total_points: number;
  matchdays_played: number;
}

export interface SeasonChampion {
  season_id: number;
  season_name: string;
  entries: PodiumEntry[];
}

export interface CareerEntry {
  user_id: number;
  display_name: string;
  seasons_played: number;
  championships: number;
  podiums: number;
  total_points: number;
  total_matchdays: number;
  avg_points: number;
  best_finish: number;
  best_season_name: string;
}

export interface AllTimeRecord {
  label: string;
  value: string;
  detail: string;
}

export interface GroupPoints {
  group_name: string;
  avg_points: number;
}

export interface SeasonGroupResult {
  season_id: number;
  season_name: string;
  winner: string;
  loser: string;
  groups: GroupPoints[];
}

export interface GroupMemberEntry {
  participant_id: number;
  display_name: string;
  total_points: number;
}

export interface GroupStandingEntry {
  rank: number;
  group_name: string;
  total_points: number;
  avg_points: number;
  member_count: number;
  members: GroupMemberEntry[];
}

export interface GroupStandingsResponse {
  season_id: number;
  season_name: string;
  groups: GroupStandingEntry[];
}

export interface PalmaresResponse {
  champions: SeasonChampion[];
  career: CareerEntry[];
  records: AllTimeRecord[];
  group_history: SeasonGroupResult[];
}

// ---------------------------------------------------------------------------
// Draft Value Predictions
// ---------------------------------------------------------------------------

export interface DraftValuePlayer {
  player_id: number;
  display_name: string;
  team_name: string;
  position: string;
  photo_path: string | null;
  games_played: number;
  seasons_played: number;
  avg_points: number;
  total_points: number;
  ensemble_score: number;
  simple_avg: number;
  second_half_score: number | null;
  productivity_score: number;
  stability_score: number;
  trend_score: number | null;
  career_trend_pct: number | null;
  marca_avg: number | null;
  as_avg: number | null;
  availability: number;
  consistency: number;
  second_half_avg: number | null;
  goals: number;
  assists: number;
  signal: string;
  signal_reasons: string[];
  weight_current?: number | null;
  // Draft board: value over positional replacement (cross-position axis).
  vorp?: number | null;
  replacement_level?: number | null;
  position_rank?: number | null;
}

export interface DraftValueResponse {
  season_id: number;
  season_name: string;
  matchdays_played: number;
  draft_type: string;
  peso_historico: number;
  model_info: Record<string, string>;
  players: DraftValuePlayer[];
}

// --- Tournaments (Mundial, Eurocopa, ...) ---

export interface TournamentTeamStanding {
  team_id: number;
  team_name: string;
  short_name: string | null;
  logo_path: string | null;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_diff: number;
  points: number;
}

export interface TournamentGroup {
  name: string;
  teams: TournamentTeamStanding[];
}

export interface TournamentGroupsResponse {
  season_id: number;
  season_name: string;
  tournament_type: string | null;
  groups: TournamentGroup[];
}

export interface BracketMatch {
  match_id: number | null;
  home_team_id: number | null;
  home_team_name: string | null;
  home_logo: string | null;
  home_score: number | null;
  away_team_id: number | null;
  away_team_name: string | null;
  away_logo: string | null;
  away_score: number | null;
  played: boolean;
  match_code?: string | null;
  home_placeholder?: string | null;
  away_placeholder?: string | null;
  label?: string | null;
  home_provisional_team_id?: number | null;
  home_provisional_team_name?: string | null;
  home_provisional_logo?: string | null;
  away_provisional_team_id?: number | null;
  away_provisional_team_name?: string | null;
  away_provisional_logo?: string | null;
}

export interface BracketRound {
  name: string;
  matchday: number;
  matches: BracketMatch[];
}

export interface BracketResponse {
  season_id: number;
  season_name: string;
  rounds: BracketRound[];
}

export interface BracketPredictions {
  /** group letter -> [team_id_1st, team_id_2nd, team_id_3rd, team_id_4th] */
  groups?: Record<string, (number | null)[]>;
  /** Set of 8 group letters whose 3rd-placed team advances. */
  best_thirds?: string[];
  /** match_code -> winning team_id. Used for R32 through Final + 3rd. */
  match_winners?: Record<string, number | null>;
}

export interface TournamentPrediction {
  id: number;
  season_id: number;
  user_id: number;
  display_name: string | null;
  winner_team_id: number | null;
  winner_team_name: string | null;
  top_scorer_player_id: number | null;
  top_scorer_player_name: string | null;
  best_player_id: number | null;
  best_player_name: string | null;
  dark_horse_team_id: number | null;
  dark_horse_team_name: string | null;
  notes: string | null;
  bonus_points: number;
  bracket_predictions?: BracketPredictions | null;
}

export interface PredictionsListResponse {
  season_id: number;
  season_name: string;
  predictions: TournamentPrediction[];
}

export interface PredictionRequest {
  winner_team_id: number | null;
  top_scorer_player_id: number | null;
  best_player_id: number | null;
  dark_horse_team_id: number | null;
  notes: string | null;
  bracket_predictions?: BracketPredictions | null;
}

// ---------------------------------------------------------------------------
// Draft retrospective (admin) — backend: stats/admin/drafts/...
// ---------------------------------------------------------------------------

export interface RetroPick {
  pick_number: number;
  round_number: number;
  participant_id: number;
  participant_display_name: string;
  player_id: number;
  player_name: string;
  position: string;
  team_name: string;
  photo_path: string | null;
  season_total_points: number;
  season_avg_pts: number;
  matchdays_played: number;
  slot_median_total_points: number | null;
  delta_vs_slot: number | null;
  tag: "steal" | "bust" | "normal" | string;
}

export interface DraftRetrospectiveResponse {
  draft_id: number;
  season_id: number;
  season_name: string;
  phase: string;
  n_picks: number;
  picks: RetroPick[];
}

export interface PickPoint {
  pick_number: number;
  round_number: number;
  total_points: number;
  avg_points: number;
  matchdays_played: number;
  position: string;
  player_id: number;
  player_name: string;
  team_name: string;
  season_id: number;
  season_name: string;
  phase: string;
  participant_display_name: string;
}

export interface DraftScatterResponse {
  season_ids: number[];
  phases: string[];
  n_points: number;
  points: PickPoint[];
  slot_curve: Record<number, number>;
}

export interface BacktestPoint {
  player_id: number;
  player_name: string;
  position: string;
  seasons_history: number;
  predicted_effective_score: number;
  predicted_signal: "strong_buy" | "buy" | "hold" | "avoid" | string;
  predicted_tier: "elite" | "solid" | "normal" | "weak" | string;
  actual_total_points: number;
  actual_avg_points: number;
  actual_matchdays_played: number;
}

export interface SignalBucket {
  n: number;
  mean_actual: number;
  median_actual: number;
}

export interface BacktestResponse {
  season_id: number;
  season_name: string;
  n_players: number;
  spearman_rank_correlation: number;
  by_signal: Record<string, SignalBucket>;
  by_tier: Record<string, SignalBucket>;
  points: BacktestPoint[];
}

export interface BestPickHighlight {
  player_name: string;
  season_name: string;
  pick_number: number;
  round_number: number;
  delta_vs_slot: number;
}

export interface ParticipantIQEntry {
  participant_id: number;
  display_name: string;
  n_drafts: number;
  total_picks: number;
  sum_delta_vs_slot: number;
  mean_delta_per_pick: number;
  best_pick: BestPickHighlight | null;
  worst_pick: BestPickHighlight | null;
  by_round: Record<number, number>;
}

export interface ParticipantIQResponse {
  phase: string;
  min_seasons: number;
  participants: ParticipantIQEntry[];
}

// ---------------------------------------------------------------------------
// Marca-rating admin tool (/admin/marca). Backend: scraping/schemas_marca.py
// ---------------------------------------------------------------------------

/** Values the dropdown emits and the BD stores. The UI renders
 *  "1"..."4" as ★...★★★★ via `starsForRating()` in
 *  `src/lib/marca-rating.ts`. `null` ⇒ "no jugó" (BD NULL, 0 pts). */
export type MarcaRatingValue = "1" | "2" | "3" | "4" | "SC" | "-" | null;

export interface MarcaPlayerRow {
  player_id: number;
  display_name: string;
  team_id: number;
  team_name: string;
  /** Estado actual en BD. `null` = sin player_stats todavía. */
  marca_rating: string | null;
  as_picas?: string | null;
  /** Cuando es true, el scrape no machaca as_picas. */
  as_picas_admin_set?: boolean;
  minutes_played: number;
  position: string;
  aliases?: string | null;
}

export interface MarcaRosterResponse {
  match_id: number;
  match_label: string;
  matchday_number: number;
  home: MarcaPlayerRow[];
  away: MarcaPlayerRow[];
}

export interface MarcaAssignment {
  player_id: number;
  /** `null` ⇒ "no jugó", persistido como NULL en player_stats. */
  marca_rating: MarcaRatingValue;
}

export interface MarcaApplyRequest {
  match_id: number;
  assignments: MarcaAssignment[];
}

export type PicasValue = "1" | "2" | "3" | "SC" | "-" | null;

export interface PicasAssignment {
  player_id: number;
  as_picas: PicasValue;
}

export interface PicasApplyRequest {
  match_id: number;
  assignments: PicasAssignment[];
}

export interface MarcaPreviewRow {
  surname_clean: string;
  stars: number;             // 0..4
  is_substitute: boolean;
  minute: number | null;
  raw_text: string;
  confidence: number;        // 0..1
  /** "sc" / "dash" / null when stars=0 and a text marker was found. */
  explicit_marker?: string | null;
}

export interface MarcaPreviewMatch {
  row: MarcaPreviewRow;
  player_id: number;
  player_name: string;
  /**
   * Server-resolved suggestion. null = "no jugó" (no stars + no marker).
   * Priority: explicit_marker (s/c → "SC", dash → "-") > stars > null.
   */
  marca_rating: string | null;
}

export interface MarcaPreviewUnmatched {
  row: MarcaPreviewRow;
  candidates: MarcaPlayerRow[];
}

export interface MarcaPreviewResponse {
  match_id: number;
  match_label: string;
  matchday_number: number;
  roster: MarcaPlayerRow[];
  matches: MarcaPreviewMatch[];
  unmatched: MarcaPreviewUnmatched[];
}

// ---------------------------------------------------------------------------
// 🍔 Burger Ranking (/burger-ranking). Backend: burger_ranking/schemas.py
// ---------------------------------------------------------------------------

/** One goal that contributed to a participant's burger total. */
export interface BurgerGoal {
  matchday_number: number;
  player_id: number;
  player_name: string;
  team_name: string;
  goals: number; // 1, 2, … goals from that player that matchday
}

export interface BurgerEntry {
  participant_id: number;
  display_name: string;
  total: number;
  goals: BurgerGoal[];
}

export interface BurgerRankingResponse {
  season_id: number;
  entries: BurgerEntry[];
}

// Bench Ranking — players lined up that played 0 minutes.

export interface BenchedPlayer {
  matchday_number: number;
  player_id: number;
  player_name: string;
  team_name: string;
  position: string;
}

export interface BenchEntry {
  participant_id: number;
  display_name: string;
  total: number;
  players: BenchedPlayer[];
}

export interface BenchRankingResponse {
  season_id: number;
  entries: BenchEntry[];
}

// Survivors Ranking — tournaments only: how many owned players are still in.

export interface SurvivorPlayer {
  player_id: number;
  player_name: string;
  team_name: string;
  position: string;
  alive: boolean;
}

export interface SurvivorEntry {
  participant_id: number;
  display_name: string;
  alive_count: number;
  eliminated_count: number;
  total: number;
  players: SurvivorPlayer[];
}

export interface SurvivorsResponse {
  season_id: number;
  group_stage_done: boolean;
  entries: SurvivorEntry[];
}

// Combined response for the /ranking page.

export interface RankingsResponse {
  season_id: number;
  burger: BurgerRankingResponse;
  bench: BenchRankingResponse;
  /** Tournaments only; null for leagues. */
  survivors?: SurvivorsResponse | null;
}
