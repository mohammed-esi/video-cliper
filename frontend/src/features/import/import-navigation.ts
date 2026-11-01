/** Query param that forces a new ImportScreen mount (avoids router cache state). */
export const FRESH_IMPORT_QUERY_PARAM = "freshImport";

export function buildFreshImportHomePath(
  nonce: string | number = Date.now(),
): string {
  const params = new URLSearchParams();
  params.set(FRESH_IMPORT_QUERY_PARAM, String(nonce));
  return `/?${params.toString()}`;
}

export function resolveImportScreenMountKey(
  searchParams: Pick<URLSearchParams, "get">,
): string {
  const fresh = searchParams.get(FRESH_IMPORT_QUERY_PARAM);
  return fresh ?? "default";
}

export function navigateToFreshImport(
  push: (href: string) => void,
  nonce: string | number = Date.now(),
): void {
  push(buildFreshImportHomePath(nonce));
}
