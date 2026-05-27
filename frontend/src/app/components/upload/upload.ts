import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';

import { TransferService, UploadResult } from '../../services/transfer.service';

@Component({
  selector: 'app-upload',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    MatButtonToggleModule,
    MatIconModule,
    MatSnackBarModule,
    MatTooltipModule,
    MatDividerModule,
  ],
  templateUrl: './upload.html',
  styleUrl: './upload.scss',
})
export class UploadComponent {
  selectedFile: File | null = null;
  password   = '';
  expiresIn  = '24h';
  dragOver   = false;

  encryptPct = 0;
  uploadPct  = 0;
  uploading  = false;
  result: UploadResult | null = null;

  constructor(
    private transfer: TransferService,
    private snack: MatSnackBar,
  ) {}

  onDragOver(e: DragEvent) {
    e.preventDefault();
    this.dragOver = true;
  }

  onDragLeave() {
    this.dragOver = false;
  }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.dragOver = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) this.selectedFile = file;
  }

  onFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    const file  = input.files?.[0];
    if (file) this.selectedFile = file;
  }

  formatBytes(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
    if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
    return `${(n / 1024 ** 3).toFixed(2)} GB`;
  }

  async startUpload() {
    if (!this.selectedFile || !this.password) return;
    this.uploading  = true;
    this.result     = null;
    this.encryptPct = 0;
    this.uploadPct  = 0;

    try {
      this.result = await this.transfer.uploadFile(
        this.selectedFile,
        this.password,
        this.expiresIn,
        (pct) => { this.uploadPct = pct; },
      );
    } catch (e: any) {
      this.snack.open(e.message ?? 'Upload fehlgeschlagen', 'OK', { duration: 5000 });
    } finally {
      this.uploading = false;
    }
  }

  async copyToClipboard(text: string, label: string) {
    await navigator.clipboard.writeText(text);
    this.snack.open(`${label} kopiert`, undefined, { duration: 2000 });
  }

  reset() {
    this.selectedFile = null;
    this.password     = '';
    this.result       = null;
    this.uploadPct    = 0;
  }
}
