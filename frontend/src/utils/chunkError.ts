// The messages browsers give when a page's code file could not be loaded: Chrome and Edge, Firefox,
// Safari, and the older webpack-style wording some tools still produce.
const CHUNK_LOAD_ERROR =
  /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS|Loading chunk [\w-]+ failed|ChunkLoadError/i;

/**
 * Whether `error` is a page's code file that could not be loaded. After a new release the old file
 * is gone, and Hosting answers the missing address with the home page, so a tab opened before the
 * release fails on every page it has not shown yet. Asking again in the same page cannot help: the
 * browser keeps the failed answer until the page is loaded again (NF-HR-004).
 */
export function isChunkLoadError(error: unknown): boolean {
  const text = error instanceof Error ? `${error.name} ${error.message}` : String(error);
  return CHUNK_LOAD_ERROR.test(text);
}
