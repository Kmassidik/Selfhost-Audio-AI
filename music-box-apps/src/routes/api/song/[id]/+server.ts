import { json, error } from '@sveltejs/kit';
import { rm } from 'node:fs/promises';
import { join } from 'node:path';
import { require_admin } from '$lib/server/gate.js';
import { get_song } from '$lib/db/library.js';
import type { RequestHandler } from './$types';

/** /api/song/{id} — one song with its words, for the details drawer. */
export const GET: RequestHandler = async ({ params, locals }) => {
	const song = await get_song(locals.sql, params.id, locals.listener);
	if (!song) throw error(404, 'no such song');
	return json(song);
};

/**
 * Remove a song: the row, and only the row. The bytes live on a read-only
 * mount here — the worker owns them and sweeps the orphans (it is the one
 * process allowed to touch the data tree).
 */
export const DELETE: RequestHandler = async ({ params, locals }) => {
	require_admin(locals);

	const [song] = await locals.sql`SELECT id FROM songs WHERE id = ${params.id}`;
	if (!song) throw error(404, 'no such song');

	await locals.sql`DELETE FROM songs WHERE id = ${params.id}`;
	return json({ removed: params.id, files: 'the worker will sweep them' });
};
