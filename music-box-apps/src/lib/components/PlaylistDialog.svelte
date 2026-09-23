<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { playlist_dialog } from '$lib/domain/playlist-dialog.svelte.js';

	/**
	 * File a song. A visitor needs no account to have playlists, so this is a
	 * plain list of their own plus a box for a new name.
	 */
	type Playlist = { id: number; name: string; songs: number };

	let playlists = $state<Playlist[]>([]);
	let name = $state('');
	let note = $state('');
	let busy = $state(false);
	let loaded_for = $state<string | null>(null);

	$effect(() => {
		const song = playlist_dialog.song_id;
		if (!song) {
			loaded_for = null;
			return;
		}
		if (loaded_for === song) return;
		loaded_for = song;
		name = '';
		note = '';
		fetch('/api/playlists')
			.then((r) => r.json())
			.then((d: { items: Playlist[] }) => (playlists = d.items))
			.catch(() => undefined);
	});

	async function add_to(id: number) {
		if (!playlist_dialog.song_id) return;
		busy = true;
		try {
			const r = await fetch(`/api/playlists/${id}/songs`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ song_id: playlist_dialog.song_id })
			});
			if (!r.ok) throw new Error('could not add it');
			const list = playlists.find((p) => p.id === id);
			if (list) list.songs += 1;
			note = `Added to ${list?.name ?? 'the playlist'}`;
			await invalidateAll();
			setTimeout(() => playlist_dialog.close(), 500);
		} catch (e) {
			note = (e as Error).message;
		} finally {
			busy = false;
		}
	}

	async function create_and_add() {
		if (!name.trim()) return;
		busy = true;
		try {
			const r = await fetch('/api/playlists', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name })
			});
			if (!r.ok) throw new Error('could not make it');
			const made = (await r.json()) as Playlist;
			playlists = [{ ...made }, ...playlists];
			name = '';
			await add_to(made.id);
		} catch (e) {
			note = (e as Error).message;
		} finally {
			busy = false;
		}
	}
</script>

{#if playlist_dialog.song_id}
	<div
		class="fixed inset-0 z-[70] grid place-items-center px-6 bg-black/40 backdrop-blur-sm"
		role="dialog"
		aria-label="Add to playlist"
		onclick={(e) => e.target === e.currentTarget && playlist_dialog.close()}
	>
		<div class="glass-panel rounded-2xl p-6 w-full max-w-sm">
			<div class="flex items-center justify-between mb-4">
				<div>
					<h2 class="font-bold">Add to playlist</h2>
					<p class="text-xs text-muted truncate">{playlist_dialog.song_title || 'this song'}</p>
				</div>
				<button class="text-muted hover:text-ink text-xl" aria-label="Close" onclick={() => playlist_dialog.close()}>
					<i class="ph ph-x"></i>
				</button>
			</div>

			{#if playlists.length}
				<ul class="max-h-56 overflow-y-auto no-scrollbar mb-4 space-y-1">
					{#each playlists as p (p.id)}
						<li>
							<button
								class="flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-glasshover text-left disabled:opacity-50"
								disabled={busy}
								onclick={() => add_to(p.id)}
							>
								<span class="truncate">{p.name}</span>
								<span class="text-[11px] text-muted">{p.songs}</span>
							</button>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="text-xs text-muted mb-4">No playlists yet — name one below.</p>
			{/if}

			<div class="flex gap-2">
				<input
					bind:value={name}
					placeholder="New playlist"
					onkeydown={(e) => e.key === 'Enter' && create_and_add()}
					class="flex-1 bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
				/>
				<button
					class="px-4 rounded-full bg-accent text-white text-sm font-semibold disabled:opacity-50"
					disabled={busy || !name.trim()}
					onclick={create_and_add}
				>Create</button>
			</div>

			{#if note}<p class="text-xs text-muted mt-3">{note}</p>{/if}
		</div>
	</div>
{/if}
