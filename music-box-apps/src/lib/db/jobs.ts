import type { Sql } from './index.js';

/**
 * The queue, in Postgres. The web app never touches a graphics card: it
 * writes a row here, and the worker — one job at a time — claims it. The
 * shapes match what the create page already reads.
 */

type Job = {
	id: number;
	song_id: string | null;
	model: string;
	title: string;
	params: Record<string, unknown>;
	status: string;
	position: number;
	error: string;
	wall_s: number | null;
	created_at: string;
};

export async function enqueue(
	sql: Sql,
	model: string,
	params: Record<string, unknown>,
	title: string,
	creator = ''
): Promise<number> {
	const [row] = await sql<[{ id: number }]>`
		INSERT INTO jobs (model, title, params, status, created_at, creator_id)
		VALUES (${model}, ${title}, ${sql.json(params as never)}, 'queued',
		        to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'), ${creator})
		RETURNING id`;
	return row.id;
}

/** Where each waiting job stands in line: 1 is next off the rank. */
export async function positions(sql: Sql): Promise<Map<number, number>> {
	const rows = await sql<{ id: number }[]>`
		SELECT id FROM jobs WHERE status = 'queued' ORDER BY id`;
	return new Map(rows.map((r, i) => [r.id, i + 1]));
}

export async function recent(sql: Sql, limit = 50): Promise<Job[]> {
	const place = await positions(sql);
	const rows = await sql<Omit<Job, 'position'>[]>`
		SELECT id, song_id, model, title, params, status, error, wall_s, created_at
		FROM jobs ORDER BY id DESC LIMIT ${limit}`;
	return rows.map((r) => ({ ...r, position: place.get(r.id) ?? 0 }));
}

export async function queue_depth(sql: Sql): Promise<{ queued: number; running: number }> {
	const [row] = await sql<[{ queued: number; running: number }]>`
		SELECT
		  COUNT(*) FILTER (WHERE status = 'queued')::int AS queued,
		  COUNT(*) FILTER (WHERE status = 'running')::int AS running
		FROM jobs`;
	return { queued: row?.queued ?? 0, running: row?.running ?? 0 };
}

/** Only a job still waiting may be taken out; a running one belongs to the cards. */
export async function cancel(sql: Sql, id: number): Promise<boolean> {
	const rows = await sql`DELETE FROM jobs WHERE id = ${id} AND status = 'queued' RETURNING id`;
	return rows.length > 0;
}
