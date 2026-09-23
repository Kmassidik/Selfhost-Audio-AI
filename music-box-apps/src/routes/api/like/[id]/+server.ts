import { json, error } from '@sveltejs/kit';
import { ensure_listener } from '$lib/db/listeners.js';
import type { RequestHandler } from './$types';

/**
 * Likes belong to the listener the cookie names. An anonymous visitor can
 * like without ever signing in; the answer is their own like, not a shared
 * one, and no one else can remove it.
 */
export const POST: RequestHandler = async ({ params, locals }) => {
	const [song] = await locals.sql`SELECT id FROM songs WHERE id = ${params.id} AND visible = TRUE`;
	if (!song) throw error(404, 'no such song');

	await ensure_listener(locals.sql, locals.listener);
	await locals.sql`
		INSERT INTO likes (listener_id, song_id, created_at)
		VALUES (${locals.listener}, ${params.id}, to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'))
		ON CONFLICT DO NOTHING`;
	return json({ liked: true });
};

export const DELETE: RequestHandler = async ({ params, locals }) => {
	await locals.sql`DELETE FROM likes WHERE listener_id = ${locals.listener} AND song_id = ${params.id}`;
	return json({ liked: false });
};
