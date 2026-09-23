// See https://svelte.dev/docs/kit/types#app.d.ts
declare global {
	namespace App {
		interface Locals {
			sql: import('$lib/db/index.js').Sql;
			user: { id: string; username: string; role: string } | null;
			/** this browser's anonymous identity; the key likes and playlists use */
			listener: string;
		}
	}
}

export {};
