import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class CryptoService {

  async deriveKey(password: string, salt: Uint8Array): Promise<CryptoKey> {
    const pwKey = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(password),
      'PBKDF2',
      false,
      ['deriveKey'],
    );
    return crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt, iterations: 100_000, hash: 'SHA-256' },
      pwKey,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt'],
    );
  }

  async encryptChunk(key: CryptoKey, chunk: Uint8Array): Promise<Uint8Array> {
    const iv        = crypto.getRandomValues(new Uint8Array(12));
    const encrypted = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, chunk);
    const ciphertext = new Uint8Array(encrypted, 0, encrypted.byteLength - 16);
    const tag        = new Uint8Array(encrypted, encrypted.byteLength - 16);
    const blockLen   = new Uint8Array(4);
    new DataView(blockLen.buffer).setUint32(0, ciphertext.byteLength, false);
    return this.concat([blockLen, iv, tag, ciphertext]);
  }

  async decryptChunk(key: CryptoKey, iv: Uint8Array, tag: Uint8Array, cipher: Uint8Array): Promise<ArrayBuffer> {
    const combined = this.concat([cipher, tag]);
    return crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, combined);
  }

  concat(arrays: Uint8Array[]): Uint8Array {
    const total = arrays.reduce((s, a) => s + a.byteLength, 0);
    const result = new Uint8Array(total);
    let offset = 0;
    for (const arr of arrays) {
      result.set(arr, offset);
      offset += arr.byteLength;
    }
    return result;
  }
}
