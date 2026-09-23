<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { page } from '$app/state';
	import { theme } from '$lib/theme.svelte.js';

	/**
	 * The sidebar carries only what the box can do: Home, All songs, Liked,
	 * the categories that have songs, this visitor's playlists, the theme
	 * switch, and — for the owner — the way to make a song.
	 */
	let {
		categories,
		stats,
		playlists,
		user,
		is_admin
	} = $props<{
		categories: { tag: string; songs: number }[];
		stats: { songs: number; seconds: number; liked: number };
		playlists: { id: number; name: string; songs: number }[];
		user: { name: string; email: string } | null;
		is_admin: boolean;
	}>();

	let q = $state('');
	let open_mobile = $state(false);
	let menu_open = $state(false);
	let new_playlist = $state('');
	let timer: ReturnType<typeof setTimeout> | undefined;

	const params = $derived(page.url.searchParams);
	const view = $derived(params.get('view') ?? 'home');
	const tag = $derived(params.get('tag') ?? '');
	const playlist = $derived(Number(params.get('playlist') ?? 0));

	function go(url: string) {
		open_mobile = false;
		menu_open = false;
		goto(url);
	}

	function search(value: string) {
		q = value;
		clearTimeout(timer);
		timer = setTimeout(() => go(value.trim() ? `/?q=${encodeURIComponent(value.trim())}` : '/'), 250);
	}

	async function make_playlist() {
		const name = new_playlist.trim();
		if (!name) return;
		const r = await fetch('/api/playlists', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name })
		});
		if (r.ok) {
			const made = (await r.json()) as { id: number };
			new_playlist = '';
			await invalidateAll();
			go(`/?playlist=${made.id}`);
		}
	}

	async function sign_out() {
		await fetch('/api/logout', { method: 'POST' });
		menu_open = false;
		goto('/', { invalidateAll: true });
	}

	const nav_item = (active: boolean) =>
		active
			? 'flex items-center gap-3 px-3 py-1.5 rounded-md bg-accent text-white text-sm font-medium'
			: 'flex items-center gap-3 px-3 py-1.5 rounded-md text-ink hover:bg-glasshover text-sm font-medium';
</script>

<button
	class="md:hidden fixed top-3 left-3 z-40 glass-panel rounded-lg p-2"
	aria-label="Open menu"
	onclick={() => (open_mobile = true)}
><i class="ph ph-list text-lg"></i></button>

<aside
	class="fixed md:relative z-50 w-[260px] h-full glass-panel no-edge flex flex-col pt-4 shrink-0 transition-transform duration-300
	       {open_mobile ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}"
>
	<div class="hidden md:flex items-center gap-3 px-5 py-4 shrink-0">
		<span class="w-8 h-8 rounded-lg bg-accent text-white grid place-items-center">
			<i class="ph-fill ph-music-note text-sm"></i>
		</span>
		<span class="font-bold tracking-tight">Dalang Music Box</span>
	</div>

	<button
		class="md:hidden absolute top-4 right-4 text-muted"
		aria-label="Close menu"
		onclick={() => (open_mobile = false)}
	><i class="ph ph-x text-xl"></i></button>

	<div class="px-3 mt-12 md:mt-0 mb-4 shrink-0">
		<div class="relative w-full">
			<i class="ph ph-magnifying-glass absolute left-3 top-1/2 -translate-y-1/2 text-muted"></i>
			<input
				type="text"
				placeholder="Search songs, styles, lyrics"
				value={params.get('q') ?? ''}
				oninput={(e) => search(e.currentTarget.value)}
				class="w-full bg-glasshover border border-line rounded-lg py-1.5 pl-9 pr-3 text-sm placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent"
			/>
		</div>
	</div>

	<nav class="flex-1 min-h-0 overflow-y-auto no-scrollbar px-2 pb-4 space-y-6">
		<ul class="space-y-0.5">
			<li>
				<a href="/" class={nav_item(view === 'home' && !params.get('q') && !playlist)}>
					<i class="ph-fill ph-house text-lg"></i> Home
				</a>
			</li>
			<li>
				<a href="/?view=all" class={nav_item(view === 'all')} onclick={(e) => (e.preventDefault(), go('/?view=all'))}>
					<i class="ph ph-music-notes-simple text-lg"></i> All songs
					<span class="ml-auto text-[11px] text-muted">{stats.songs}</span>
				</a>
			</li>
			<li>
				<a href="/?view=liked" class={nav_item(view === 'liked')} onclick={(e) => (e.preventDefault(), go('/?view=liked'))}>
					<i class="ph ph-heart text-lg"></i> Liked
					<span class="ml-auto text-[11px] text-muted">{stats.liked}</span>
				</a>
			</li>
		</ul>

		<div>
			<p class="px-3 text-xs font-semibold text-muted mb-1">Playlists</p>
			{#if playlists.length}
				<ul class="space-y-0.5 mb-1">
					{#each playlists as p (p.id)}
						<li>
							<a
								href="/?playlist={p.id}"
								class={nav_item(playlist === p.id)}
								onclick={(e) => (e.preventDefault(), go(`/?playlist=${p.id}`))}
							>
								<i class="ph ph-queue text-lg"></i>
								<span class="truncate">{p.name}</span>
								<span class="ml-auto text-[11px] text-muted">{p.songs}</span>
							</a>
						</li>
					{/each}
				</ul>
			{/if}
			<div class="px-3 flex gap-2">
				<input
					bind:value={new_playlist}
					placeholder="New playlist"
					onkeydown={(e) => e.key === 'Enter' && make_playlist()}
					class="flex-1 bg-glasshover border border-line rounded-md py-1 px-2 text-xs placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-accent"
				/>
				<button
					class="text-muted hover:text-ink px-1"
					title="Create playlist"
					disabled={!new_playlist.trim()}
					onclick={make_playlist}
				><i class="ph ph-plus"></i></button>
			</div>
		</div>

		<div>
			<p class="px-3 text-xs font-semibold text-muted mb-1">Categories</p>
			{#if categories.length}
				<ul class="space-y-0.5">
					{#each categories as c (c.tag)}
						<li>
							<a
								href="/?tag={encodeURIComponent(c.tag)}"
								class={nav_item(tag === c.tag)}
								onclick={(e) => (e.preventDefault(), go(`/?tag=${encodeURIComponent(c.tag)}`))}
							>
								<i class="ph ph-vinyl-record text-lg"></i>
								<span class="truncate">{c.tag}</span>
								<span class="ml-auto text-[11px] text-muted">{c.songs}</span>
							</a>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="px-3 text-xs text-muted">No categories yet</p>
			{/if}
		</div>
	</nav>

	<div class="shrink-0 glass-panel no-edge">
		<div class="px-4 pt-3 text-[11px] text-muted">
			{stats.songs} songs · {(stats.seconds / 3600).toFixed(1)} h
		</div>

		<!-- the theme switch is a plain control; signing in is a plain link.
		     Neither hides behind the other. -->
		<div class="flex items-center gap-2 px-3 py-2">
			<button
				class="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-glasshover hover:text-ink"
				title={theme.current === 'dark' ? 'Light theme' : 'Dark theme'}
				aria-label="Switch theme"
				onclick={theme.toggle}
			><i class="ph-fill {theme.current === 'dark' ? 'ph-sun' : 'ph-moon'} text-lg"></i></button>

			{#if user}
				<button
					class="flex min-w-0 flex-1 items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-glasshover text-left"
					onclick={() => (menu_open = !menu_open)}
				>
					<span class="flex min-w-0 items-center gap-2">
						<span class="w-7 h-7 shrink-0 rounded-full bg-accent text-white grid place-items-center text-xs font-bold">
							{user.username.slice(0, 1).toUpperCase()}
						</span>
						<span class="text-sm font-medium truncate">{user.username}</span>
					</span>
					<i class="ph ph-caret-{menu_open ? 'down' : 'up'} text-muted text-sm"></i>
				</button>
			{:else}
				<a
					href="/login"
					class="flex min-w-0 flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium hover:bg-glasshover"
				>
					<span class="w-7 h-7 shrink-0 rounded-full bg-glasshover grid place-items-center">
						<i class="ph ph-user text-sm text-muted"></i>
					</span>
					Sign in
				</a>
			{/if}
		</div>

		{#if user && menu_open}
			<div class="px-3 pb-3 flex flex-col gap-1">
				<a href="/create" class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-glasshover">
					<i class="ph ph-plus-circle text-lg"></i> Create song
				</a>
				{#if is_admin}
					<a href="/users" class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-glasshover">
						<i class="ph ph-users text-lg"></i> Users
					</a>
				{/if}
				<button
					class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-accent hover:bg-glasshover text-left"
					onclick={sign_out}
				><i class="ph ph-sign-out text-lg"></i> Sign out</button>
			</div>
		{/if}
	</div>
</aside>
