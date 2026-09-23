import { json, error } from '@sveltejs/kit';
import { count_admins, remove_user, set_password } from '$lib/server/session.js';
import { require_admin } from '$lib/server/gate.js';
import type { RequestHandler } from './$types';

/** Reset someone's password, or remove them — with the two rules that matter. */
export const PATCH: RequestHandler = async ({ params, request, locals }) => {
	require_admin(locals);
	const body = (await request.json().catch(() => ({}))) as { password?: string };
	if ((body.password ?? '').length < 8) throw error(400, 'a password of at least 8 characters');
	if (!(await set_password(locals.sql, params.id, body.password as string))) throw error(404, 'no such account');
	return json({ ok: true });
};

export const DELETE: RequestHandler = async ({ params, locals }) => {
	require_admin(locals);

	// an admin cannot delete themselves, and cannot empty the register of admins
	if (params.id === locals.user?.id) throw error(400, 'that is your own account');
	const [target] = await locals.sql<{ role: string }[]>`
		SELECT role FROM users WHERE id = ${params.id}`;
	if (!target) throw error(404, 'no such account');
	if (target.role === 'admin' && (await count_admins(locals.sql)) <= 1) {
		throw error(400, 'the last admin cannot be removed');
	}

	await remove_user(locals.sql, params.id);
	return json({ ok: true });
};
