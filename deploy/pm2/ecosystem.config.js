// PM2 configuration for Liga VPV frontend (Next.js standalone)
// Install: pm2 start /opt/vpv/deploy/pm2/ecosystem.config.js
// Manage:  pm2 status | pm2 logs vpv-frontend | pm2 restart vpv-frontend
//
// NEXT_PUBLIC_* vars are build-time only (inlined by Next.js during `npm run build`).
// They go in frontend/.env.production, NOT here.
// Runtime secrets (NEXTAUTH_SECRET) go in frontend/.env.production.local.

module.exports = {
  apps: [
    {
      name: "vpv-frontend",
      cwd: "/opt/vpv/frontend",
      script: ".next/standalone/server.js",
      env: {
        NODE_ENV: "production",
        PORT: 3000,
        HOSTNAME: "127.0.0.1",
        NEXTAUTH_URL: "https://new.ligavpv.com",
        API_INTERNAL_URL: "http://127.0.0.1:8000/api",
      },
      instances: 1,
      autorestart: true,
      max_memory_restart: "512M",
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: "/var/log/vpv/frontend-error.log",
      out_file: "/var/log/vpv/frontend-out.log",
      merge_logs: true,
    },
  ],
};
