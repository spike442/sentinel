import { getJson, sendRequest } from "./client";
import type { PullRequestReview } from "../model";

export async function loadReviews(signal: AbortSignal): Promise<PullRequestReview[]> {
  const data = await getJson<{ reviews: PullRequestReview[] }>("/api/pr-reviews?limit=100", signal);
  return data.reviews;
}

export function checkReviews(): Promise<void> {
  return sendRequest("/api/events/pr-reviews/check", "POST", "Sentinel review check failed");
}

export function deleteReview(review: PullRequestReview): Promise<void> {
  return sendRequest(`/api/pr-reviews/${review.id}`, "DELETE", "Review deletion failed");
}

export function replayReview(review: PullRequestReview, prompt: string): Promise<void> {
  return sendRequest(`/api/pr-reviews/${review.id}/replay`, "POST", "Review replay rejected", { prompt });
}

export function fixReview(review: PullRequestReview, prompt: string): Promise<void> {
  return sendRequest(`/api/pr-reviews/${review.id}/fix`, "POST", "Fix rejected", { prompt });
}
