import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

import { TransferService } from '../../services/transfer.service';

interface FileInfo {
  filename: string;
  size_bytes: number;
  expires_at: string | null;
}

@Component({
  selector: 'app-download',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    MatIconModule,
    MatSnackBarModule,
  ],
  templateUrl: './download.html',
  styleUrl: './download.scss',
})
export class DownloadComponent implements OnInit {
  token     = '';
  password  = '';
  hidePass  = true;
  progress  = 0;
  loading   = false;
  done      = false;
  fileInfo: FileInfo | null = null;
  infoError = '';

  constructor(
    private route: ActivatedRoute,
    private transfer: TransferService,
    private snack: MatSnackBar,
  ) {}

  ngOnInit() {
    this.token = this.route.snapshot.paramMap.get('token') ?? '';
    if (this.token) this.loadInfo();
  }

  onTokenInput(value: string) {
    this.fileInfo  = null;
    this.infoError = '';
    if (value.length === 36) this.loadInfo();
  }

  async loadInfo() {
    try {
      const res = await fetch(`/api/info/${this.token}`);
      if (res.status === 404) { this.infoError = 'Token nicht gefunden.'; return; }
      if (res.status === 410) { this.infoError = 'Dieser Link ist abgelaufen.'; return; }
      if (!res.ok) { this.infoError = 'Fehler beim Laden der Dateiinfos.'; return; }
      this.fileInfo = await res.json();
    } catch {
      // info endpoint optional – silently ignore
    }
  }

  formatBytes(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
    if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
    return `${(n / 1024 ** 3).toFixed(2)} GB`;
  }

  async startDownload() {
    if (!this.token || !this.password) return;
    if (!('showSaveFilePicker' in window)) {
      this.snack.open('Dieser Browser wird nicht unterstützt. Bitte Chromium-Browser verwenden.', 'OK', { duration: 6000 });
      return;
    }

    this.loading  = true;
    this.progress = 0;
    this.done     = false;

    try {
      const filename = this.fileInfo?.filename ?? 'download';
      await this.transfer.downloadAndDecrypt(
        this.token,
        this.password,
        filename,
        (pct) => { this.progress = pct; },
      );
      this.done = true;
    } catch (e: any) {
      const msg = e.message || 'Download fehlgeschlagen';
      this.snack.open(msg.includes('operation-specific') ? 'Falsches Passwort oder beschädigte Datei.' : msg,
                      'OK', { duration: 6000 });
    } finally {
      this.loading = false;
    }
  }
}
