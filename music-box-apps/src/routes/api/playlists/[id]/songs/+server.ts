import { json, error } from '@sveltejs/kit';
import { add_song, owns } from '$lib/db/playlists.js';
import type { RequestHandler } from './$types';

/** Put a song in a playlist. The same song twice is ignored, by the database. */
export const POST: RequestHandler = async ({ params, request, locals }) => {
	const id = Number(params.id);
	if (!Number.isInteger(id)) throw error(400, 'a playlist id is a number');
	const body = (await request.json().catch(() => ({}))) as { song_id?: string };
	if (!body.song_id) throw error(400, 'which song?');
	if (!(await owns(locals.sql, locals.listener, id))) throw error(404, 'no such playlist');

	await add_song(locals.sql, locals.listener, id, body.song_id);
	return json({ ok: true });
};
