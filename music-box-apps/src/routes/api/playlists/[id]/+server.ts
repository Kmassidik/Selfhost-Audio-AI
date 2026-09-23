import { json, error } from '@sveltejs/kit';
import { delete_playlist, rename_playlist } from '$lib/db/playlists.js';
import type { RequestHandler } from './$types';

const id_of = (raw: string) => {
	const id = Number(raw);
	if (!Number.isInteger(id)) throw error(400, 'a playlist id is a number');
	return id;
};

export const PATCH: RequestHandler = async ({ params, request, locals }) => {
	const body = (await request.json().catch(() => ({}))) as { name?: string };
	if (!body.name?.trim()) throw error(400, 'a playlist needs a name');
	if (!(await rename_playlist(locals.sql, locals.listener, id_of(params.id), body.name.trim()))) {
		throw error(404, 'no such playlist');
	}
	return json({ ok: true });
};

export const DELETE: RequestHandler = async ({ params, locals }) => {
	if (!(await delete_playlist(locals.sql, locals.listener, id_of(params.id)))) {
		throw error(404, 'no such playlist');
	}
	return json({ ok: true });
};
