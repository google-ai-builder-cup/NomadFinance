/** `GET /api/v1/public/stats`. A total the backend could not read is `null`, never 0. */
export interface PublicStats {
  workers: number | null;
  contracts_checked: number | null;
  radar_reports: number | null;
  alerts_generated: number | null;
  scam_messages_checked: number | null;
  scams_flagged: number | null;
  coach_plans: number | null;
  generated_at: string;
}
