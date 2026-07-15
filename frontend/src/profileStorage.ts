export const PROFILE_TOKEN_STORAGE_KEY = 'bseu:anonymous-profile-token:v1'

function storage() {
  return typeof window === 'undefined' ? undefined : window.localStorage
}

export function readProfileToken() {
  return storage()?.getItem(PROFILE_TOKEN_STORAGE_KEY) ?? null
}

export function storeProfileToken(token: string) {
  storage()?.setItem(PROFILE_TOKEN_STORAGE_KEY, token)
}

export function removeProfileToken() {
  storage()?.removeItem(PROFILE_TOKEN_STORAGE_KEY)
}
