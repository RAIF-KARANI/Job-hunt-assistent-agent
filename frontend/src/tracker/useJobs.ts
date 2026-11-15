// The tracked jobs, kept fresh: loaded on open, and again when an agent run
// finishes (a new job or a new cover note).

import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage, getApi, onEvent } from "../bridge/bridge";
import type { ApplyAnswer, JobRow, JobStatus } from "../bridge/types";

export type FollowUpAction = "done" | "snooze" | "ignore";

export interface Move {
  job: JobRow;
  from: JobStatus;
  to: JobStatus;
}

export function useJobs() {
  const [jobs, setJobs] = useState<JobRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const jobsRef = useRef(jobs);
  jobsRef.current = jobs;

  const load = useCallback(() => {
    getApi()
      .then((api) => api.list_jobs())
      .then((rows) => {
        setJobs(rows);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  useEffect(() => {
    load();
    return onEvent((e) => {
      if (e.type === "finished") load();
    });
  }, [load]);

  /** Optimistic: the card moves at once; if saving fails it moves back. */
  const move = useCallback(
    async (id: number, to: JobStatus): Promise<Move | null> => {
      const job = jobsRef.current?.find((j) => j.id === id);
      if (!job || job.status === to) return null;
      const before = jobsRef.current;
      setJobs((rows) => rows?.map((j) => (j.id === id ? { ...j, status: to } : j)) ?? rows);
      try {
        await (await getApi()).set_status(id, to);
        load(); // picks up the new updated_at
        return { job, from: job.status, to };
      } catch (e) {
        setJobs(before);
        setError(`Couldn't change the status: ${errorMessage(e)}`);
        return null;
      }
    },
    [load],
  );

  /** 14e: "I followed up" or "Remind me in 3 days" on a job due a follow-up; 16a: "Ignore". */
  const followUp = useCallback(
    async (id: number, action: FollowUpAction): Promise<void> => {
      try {
        const api = await getApi();
        await (action === "done" ? api.followed_up(id) : action === "snooze" ? api.snooze_follow_up(id) : api.ignore_follow_up(id));
        load();
      } catch (e) {
        setError(`Couldn't save that: ${errorMessage(e)}`);
      }
    },
    [load],
  );

  /** 16i: the answer to "Did you apply?". */
  const applyAnswer = useCallback(
    async (id: number, answer: ApplyAnswer): Promise<void> => {
      try {
        await (await getApi()).apply_answer(id, answer);
        load();
      } catch (e) {
        setError(`Couldn't save that: ${errorMessage(e)}`);
      }
    },
    [load],
  );

  return { jobs, error, load, move, followUp, applyAnswer };
}
