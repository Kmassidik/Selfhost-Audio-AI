import { error } from '@sveltejs/kit';

/**
 * Two gates, and only two. Making songs needs an account — the admin's or a
 * member's. Managing accounts needs the admin.
 */
export function require_signed_in(locals: App.Locals): void {
	if (!locals.user) throw error(401, 'sign in first');
}

export function require_admin(locals: App.Locals): void {
	if (locals.user?.role !== 'admin') throw error(403, 'only the admin can do that');
}
