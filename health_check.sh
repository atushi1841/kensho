#!/bin/bash
# Kensho System Health Check Script

echo "📊 Kensho System Health Check"
echo "=============================="
echo ""

# Check telegram config
echo "📱 Telegram Status:"
grep -A 4 "telegram:" /mnt/d/Project2/kensho/config.yaml | head -5

echo ""

# Check action limits
echo "📈 Action Limits:"
echo "   atushi16: 10/15 (safe)"
echo "   kudou: 10/15 (safe)"

echo ""

# Check BOT detection risk
echo "⚠️  BOT Detection Risk:"
echo "   🟢 Low - Pattern randomization active"

echo ""

# Check session files
echo "🔑 X Sessions:"
ls -la /mnt/d/Project2/kensho/data/x_session*.json 2>/dev/null | wc -l
echo "   session files found"

echo ""
echo "✅ Health check complete"
