// PM2 configuration for Liga VPV frontend (Next.js standalone)
// Install: pm2 start deploy/pm2/ecosystem.config.js
// Manage:  pm2 status | pm2 logs vpv-frontend | pm2 restart vpv-frontend

module.exports = {
  apps: [
    {
      name: "vpv-frontend",
      cwd: "/opt/vpv/frontend",
      script: "server.js",
      env: {
        NODE_ENV: "production",
        PORT: 3000,
        HOSTNAME: "127.0.0.1",
        NEXT_PUBLIC_API_URL: "https://ligavpv.com/api",
        NEXTAUTH_URL: "https://ligavpv.com",
        // NEXTAUTH_SECRET: set in /opt/vpv/frontend/.env
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
