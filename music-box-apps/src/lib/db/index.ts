import postgres from 'postgres';

/**
 * One SQL client for the process. SQL lives in typed modules next to the
 * schema; nothing above this layer writes a string of SQL inline.
 */
export function db_factory(env: Record<string, string | undefined>) {
	const url =
		env.DATABASE_URL ?? 'postgres://music:music@127.0.0.1:5432/musicbox';
	return postgres(url, { max: 10, idle_timeout: 30 });
}

export type Sql = ReturnType<typeof db_factory>;
