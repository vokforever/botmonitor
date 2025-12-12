# Byterover MCP Rules

## Git Rules
NEVER commit .env files to the repository - they contain sensitive configuration data.

### What's forbidden:
- `.env`
- `.env.local`
- `.env.production`
- `.env.development`
- `.env.staging`
- Any files with tokens, passwords, or API keys

### Why this is critical:
1. **Data leakage**: Tokens and keys become accessible to anyone with repository access
2. **Compromise**: Attackers can gain access to your services
3. **Financial loss**: Especially critical for paid APIs and services
4. **Reputation damage**: Leakage of customer and partner data

### Correct practice:
1. **Always add .env to .gitignore** BEFORE the first commit
2. **Create .env.example** with variable examples (without real values)
3. **Use environment variables** of deployment platforms
4. **Check git status** before each commit

### If .env gets into Git:
1. IMMEDIATELY remove from history:
   ```bash
   git filter-repo --invert-paths --path .env --force
   git push origin --force --all
   ```
2. Revoke compromised tokens
3. Generate new keys
4. Update variables on servers

### Automatic protection:
- VS Code is configured to hide .env files
- .gitignore includes all .env file variants
- Check git status before every commit

**THIS RULE APPLIES TO ALL PROJECTS WITHOUT EXCEPTIONS!**
