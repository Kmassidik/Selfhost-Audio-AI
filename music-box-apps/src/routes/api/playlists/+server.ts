import { json, error } from '@sveltejs/kit';
import { create_playlist, list_playlists } from '$lib/db/playlists.js';
import type { RequestHandler } from './$types';

/** A visitor's playlists. No account is involved: the cookie's listener is enough. */
export const GET: RequestHandler = async ({ locals }) => {
	return json({ items: await list_playlists(locals.sql, locals.listener) });
};

export const POST: RequestHandler = async ({ request, locals }) => {
	const body = (await request.json().catch(() => ({}))) as { name?: string };
	if (!body.name?.trim()) throw error(400, 'a playlist needs a name');
	return json(await create_playlist(locals.sql, locals.listener, body.name.trim()));
};
