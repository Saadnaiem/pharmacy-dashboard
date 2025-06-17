# pharmacy-dashboard
analyze pharmacy sales

# Railway deployment instructions
# 1. Railway will use requirements.txt to install dependencies.
# 2. Railway will use Procfile for the start command.
# 3. Set SUPABASE_DB_URL as a Railway environment variable (from Supabase connection string).
# 4. No .render.yaml is needed for Railway, you can delete it if you want.
# 5. Example Railway environment variables:
#    SUPABASE_DB_URL=postgresql://username:password@host:port/database
#    FLASK_ENV=production
