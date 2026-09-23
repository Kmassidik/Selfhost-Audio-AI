<script lang="ts">
	import '../app.css';
	import { theme } from '$lib/theme.svelte.js';
	import { onMount } from 'svelte';

	/**
	 * The document and nothing else. Each route decides its own interface: the
	 * studio wraps itself in the shell, and sign-in and make-a-song are pages
	 * in their own right (they had a sidebar and a player bar around them,
	 * which is what made every route look like the same page).
	 */
	let { children } = $props();

	onMount(() => theme.init());
</script>

<svelte:head>
	<title>Dalang Music Box</title>
	<meta name="description" content="Songs made on three second-hand graphics cards." />
</svelte:head>

{@render children()}
