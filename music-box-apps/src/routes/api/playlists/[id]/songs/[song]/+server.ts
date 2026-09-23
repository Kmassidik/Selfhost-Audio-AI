import { json, error } from '@sveltejs/kit';
import { owns, remove_song } from '$lib/db/playlists.js';
import type { RequestHandler } from './$types';

export const DELETE: RequestHandler = async ({ params, locals }) => {
	const id = Number(params.id);
	if (!Number.isInteger(id)) throw error(400, 'a playlist id is a number');
	if (!(await owns(locals.sql, locals.listener, id))) throw error(404, 'no such playlist');
	await remove_song(locals.sql, locals.listener, id, params.song);
	return json({ ok: true });
};
