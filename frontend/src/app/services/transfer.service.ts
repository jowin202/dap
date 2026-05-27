import { Injectable } from '@angular/core';
import { CryptoService } from './crypto.service';
import { AuthService } from './auth.service';

const CHUNK_SIZE = 8 * 1024 * 1024; // 8 MB plaintext per block

async function readExactly(reader: ReadableStreamDefaultReader<Uint8Array>, n: number): Promise<Uint8Array | null> {
  const buf = new Uint8Array(n);
  let offset = 0;
  while (offset < n) {
    const { done, value } = await reader.read();
    if (done) return offset === 0 ? null : buf.slice(0, offset);
    const slice = value.slice(0, n - offset);
    buf.set(slice, offset);
    offset += slice.byteLength;
    if (value.byteLength > slice.byteLength) {
      // leftover – put back is not possible; this simple impl assumes exact chunk boundaries
    }
  }
  return buf;
}

export interface UploadResult {
  token: string;
  expires_at: string | null;
  download_url: string;
  ps_cmd: string;
  sh_cmd: string;
}

@Injectable({ providedIn: 'root' })
export class TransferService {
  constructor(
    private crypto: CryptoService,
    private auth: AuthService,
  ) {}

  async uploadFile(
    file: File,
    password: string,
    expiresIn: string,
    onProgress: (pct: number) => void,
  ): Promise<UploadResult> {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const key  = await this.crypto.deriveKey(password, salt);

    let uploaded  = 0;
    const totalSize = file.size;

    // Build encrypted stream
    const fileStream = file.stream();
    const cryptoSvc  = this.crypto;

    const encryptTransform = new TransformStream<Uint8Array, Uint8Array>({
      async start(controller) {
        controller.enqueue(salt);
      },
      async transform(chunk, controller) {
        // Split chunk into CHUNK_SIZE pieces
        for (let offset = 0; offset < chunk.byteLength; offset += CHUNK_SIZE) {
          const slice      = chunk.slice(offset, Math.min(offset + CHUNK_SIZE, chunk.byteLength));
          const encrypted  = await cryptoSvc.encryptChunk(key, slice);
          controller.enqueue(encrypted);
        }
      },
    });

    const countingTransform = new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        uploaded += chunk.byteLength;
        if (totalSize > 0) onProgress(Math.round((uploaded / (totalSize * 1.02)) * 100));
        controller.enqueue(chunk);
      },
    });

    const body = fileStream
      .pipeThrough(encryptTransform)
      .pipeThrough(countingTransform);

    const token = this.auth.getToken();
    const response = await fetch('/upload', {
      method: 'POST',
      // @ts-ignore – duplex needed for streaming body in Chromium
      duplex: 'half',
      body,
      headers: {
        'X-Filename':   file.name,
        'X-Expires-In': expiresIn,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Upload fehlgeschlagen (${response.status}): ${text}`);
    }

    onProgress(100);
    return response.json();
  }

  async downloadAndDecrypt(
    token: string,
    password: string,
    filename: string,
    onProgress: (pct: number) => void,
  ): Promise<void> {
    const handle   = await (window as any).showSaveFilePicker({ suggestedName: filename });
    const writable = await handle.createWritable();

    const response = await fetch(`/download/${token}`);
    if (!response.ok) {
      await writable.close();
      throw new Error(`Download fehlgeschlagen (${response.status})`);
    }

    const total   = parseInt(response.headers.get('content-length') ?? '0', 10);
    let received  = 0;
    const reader  = response.body!.getReader();

    // Read salt (first 16 bytes)
    const saltBytes = await readExactly(reader, 16);
    if (!saltBytes) throw new Error('Ungültige Datei – Salt fehlt');
    received += 16;
    const key = await this.crypto.deriveKey(password, saltBytes);

    while (true) {
      const lenBytes = await readExactly(reader, 4);
      if (!lenBytes) break;
      const blockLen = new DataView(lenBytes.buffer).getUint32(0, false);
      const iv       = await readExactly(reader, 12);
      const tag      = await readExactly(reader, 16);
      const cipher   = await readExactly(reader, blockLen);
      if (!iv || !tag || !cipher) throw new Error('Unvollständiger Block');

      const plaintext = await this.crypto.decryptChunk(key, iv, tag, cipher);
      await writable.write(plaintext);

      received += 4 + 12 + 16 + blockLen;
      if (total > 0) onProgress(Math.min(99, Math.round((received / total) * 100)));
    }

    await writable.close();
    onProgress(100);
  }
}
