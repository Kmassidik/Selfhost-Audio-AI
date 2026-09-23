import { json, error } from '@sveltejs/kit';
import { create_user, list_users } from '$lib/server/session.js';
import { require_admin } from '$lib/server/gate.js';
import type { RequestHandler } from './$types';

/**
 * The account register. The admin can see how many exist and add one; nobody
 * else can reach this at all, and there is no way to add yourself.
 */
export const GET: RequestHandler = async ({ locals }) => {
	require_admin(locals);
	const items = await list_users(locals.sql);
	return json({ items, total: items.length });
};

export const POST: RequestHandler = async ({ request, locals }) => {
	require_admin(locals);
	const body = (await request.json().catch(() => ({}))) as {
		username?: string;
		password?: string;
		role?: string;
	};

	const username = (body.username ?? '').trim().toLowerCase();
	const password = body.password ?? '';
	if (!/^[a-z0-9._-]{3,24}$/.test(username)) {
		throw error(400, 'a username of 3-24 letters, numbers, dot, dash or underscore');
	}
	if (password.length < 8) throw error(400, 'a password of at least 8 characters');
	const role = body.role === 'admin' ? 'admin' : 'member';

	try {
		const person = await create_user(locals.sql, username, password, role);
		return json(person, { status: 201 });
	} catch {
		throw error(409, 'that username is taken');
	}
};
