import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatIconModule } from '@angular/material/icon';

import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatCheckboxModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatIconModule,
  ],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class LoginComponent {
  username   = '';
  password   = '';
  rememberMe = false;
  loading    = false;
  hidePass   = true;

  constructor(
    private auth: AuthService,
    private router: Router,
    private snack: MatSnackBar,
  ) {}

  async onSubmit() {
    if (!this.username || !this.password) return;
    this.loading = true;
    try {
      await this.auth.login(this.username, this.password, this.rememberMe);
      this.router.navigate(['/upload']);
    } catch (e: any) {
      this.snack.open(e.message ?? 'Login fehlgeschlagen', 'OK', { duration: 4000 });
    } finally {
      this.loading = false;
    }
  }
}
