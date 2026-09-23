import { redirect } from '@sveltejs/kit';
import { list_users } from '$lib/server/session.js';

/** The register is the admin's business only. */
export const load = async ({ locals }) => {
	if (!locals.user) throw redirect(303, '/login?next=/users');
	if (locals.user.role !== 'admin') throw redirect(303, '/');
	const items = await list_users(locals.sql);
	return { items, total: items.length, user: locals.user };
};
