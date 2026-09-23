import { redirect } from '@sveltejs/kit';

/** Already signed in? The login page is not for you. */
export const load = async ({ locals, url }) => {
	if (locals.user) throw redirect(303, url.searchParams.get('next') ?? '/create');
	return {};
};
