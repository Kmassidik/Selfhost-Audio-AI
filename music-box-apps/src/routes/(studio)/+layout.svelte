<script lang="ts">
	import '../../app.css';
	import DetailsDrawer from '$lib/components/DetailsDrawer.svelte';
	import PlayerBar from '$lib/components/PlayerBar.svelte';
	import PlaylistDialog from '$lib/components/PlaylistDialog.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import { theme } from '$lib/theme.svelte.js';
	import { onMount } from 'svelte';

	let { children, data } = $props();

	onMount(() => theme.init());
</script>

<svelte:head>
	<title>Dalang Music Box</title>
	<meta name="description" content="Songs made on three second-hand graphics cards." />
</svelte:head>

<!-- The player is the last row of the shell, not a floating bar: the sidebar
     ends where the music begins, which is what the design has always shown. -->
<div class="h-screen w-full flex flex-col overflow-hidden">
	<div class="flex-1 min-h-0 flex">
		<Sidebar
			categories={data.categories}
			stats={data.stats}
			playlists={data.playlists}
			user={data.user}
			is_admin={data.is_admin}
		/>
		<main class="flex-1 min-w-0 h-full overflow-y-auto overflow-x-hidden no-scrollbar relative pt-16 md:pt-0">
			{@render children()}
		</main>
	</div>
	<PlayerBar />
	<DetailsDrawer />
</div>

<PlaylistDialog />
