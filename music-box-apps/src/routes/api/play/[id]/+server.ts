import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * A play is counted once per request; the caller already sends one per song
 * per session. The server-side brake (per listener, per window) lands with
 * sessions — until then the route only refuses songs that do not exist.
 */
export const POST: RequestHandler = async ({ params, request, locals }) => {
	const body = (await request.json().catch(() => ({}))) as { seconds?: number };
	const seconds = Number(body.seconds ?? 0) || 0;

	const [row] = await locals.sql`
		INSERT INTO plays (song_id, listener_id, played_at, seconds_played)
		SELECT ${params.id}, ${locals.listener}, to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'), ${seconds}
		WHERE EXISTS (SELECT 1 FROM songs WHERE id = ${params.id} AND visible = TRUE)
		RETURNING id`;
	if (!row) return json({ ok: false, counted: false }, { status: 404 });
	return json({ ok: true, counted: true });
};
