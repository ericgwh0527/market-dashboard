/** Decrypts portfolio.enc.json (AES-256-GCM, PBKDF2-SHA256) – mirrors dashboard/portfolio/crypto.py. */
const b64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

export const cryptoAvailable = () => window.isSecureContext && !!crypto?.subtle;

export async function deriveKey(passphrase, blob) {
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: b64(blob.salt), iterations: blob.iter, hash: "SHA-256" },
    base, { name: "AES-GCM", length: 256 },
    false,            // non-extractable: the key can be used but never read back out
    ["decrypt"],
  );
}

export async function decrypt(key, blob) {
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(blob.iv) }, key, b64(blob.ct));
  return JSON.parse(new TextDecoder().decode(pt));
}

/** Stores the derived CryptoKey (never the passphrase) in IndexedDB. */
export class KeyStore {
  constructor(db = "mdash", store = "keys", slot = "key") { Object.assign(this, { db, store, slot }); }

  #open() {
    return new Promise((res, rej) => {
      const r = indexedDB.open(this.db, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(this.store);
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
  }

  async #tx(mode, fn) {
    try {
      const db = await this.#open();
      return await new Promise((res) => {
        const t = db.transaction(this.store, mode);
        const req = fn(t.objectStore(this.store));
        t.oncomplete = () => res(req?.result ?? null);
        t.onerror = () => res(null);
      });
    } catch { return null; }
  }

  get() { return this.#tx("readonly", (s) => s.get(this.slot)); }
  set(value) { return this.#tx("readwrite", (s) => s.put(value, this.slot)); }
  clear() { return this.#tx("readwrite", (s) => s.delete(this.slot)); }
}
