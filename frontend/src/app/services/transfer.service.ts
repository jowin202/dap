import { Injectable } from '@angular/core';
import { CryptoService } from './crypto.service';
import { AuthService } from './auth.service';

const CHUNK_SIZE = 8 * 1024 * 1024; // 8 MB plaintext per block

class StreamReader {
  private buf = new Uint8Array(0);
  constructor(private reader: ReadableStreamDefaultReader<Uint8Array>) {}

  async readExactly(n: number): Promise<Uint8Array | null> {
    while (this.buf.byteLength < n) {
      const { done, value } = await this.reader.read();
      if (done) return null;
      const merged = new Uint8Array(this.buf.byteLength + value.byteLength);
      merged.set(this.buf);
      merged.set(value, this.buf.byteLength);
      this.buf = merged;
    }
    const result = this.buf.slice(0, n);
    this.buf = this.buf.slice(n);
    return result;
  }
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
    const response = await fetch('/api/upload', {
      method: 'POST',
      // @ts-ignore – duplex needed for streaming body in Chromium
      duplex: 'half',
      body,
      headers: {
        'X-Filename':   encodeURIComponent(file.name),
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

    try {
      const response = await fetch(`/api/download/${token}`);
      if (!response.ok) throw new Error(`Download fehlgeschlagen (${response.status})`);

      const total   = parseInt(response.headers.get('content-length') ?? '0', 10);
      let received  = 0;
      const sr      = new StreamReader(response.body!.getReader());

      const saltBytes = await sr.readExactly(16);
      if (!saltBytes) throw new Error('Ungültige Datei – Salt fehlt');
      received += 16;
      const key = await this.crypto.deriveKey(password, saltBytes);

      while (true) {
        const lenBytes = await sr.readExactly(4);
        if (!lenBytes) break;
        const blockLen = new DataView(lenBytes.buffer).getUint32(0, false);
        const iv       = await sr.readExactly(12);
        const tag      = await sr.readExactly(16);
        const cipher   = await sr.readExactly(blockLen);
        if (!iv || !tag || !cipher) throw new Error('Unvollständiger Block');

        const plaintext = await this.crypto.decryptChunk(key, iv, tag, cipher);
        await writable.write(plaintext);

        received += 4 + 12 + 16 + blockLen;
        if (total > 0) onProgress(Math.min(99, Math.round((received / total) * 100)));
      }

      await writable.close();
      onProgress(100);
    } catch (e) {
      await writable.abort();
      throw e;
    }
  }
}
