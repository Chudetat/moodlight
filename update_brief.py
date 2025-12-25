# Read the file
with open('app.py', 'r') as f:
    content = f.read()

old_text = '''Create a brief with exactly these three sections:

STRATEGY RECOMMENDATION:
Tell the story of this cultural moment and connect it to the client's opportunity. Be specific — reference the data. End with a strategic bet.
Example: "The bet: Own the tension between performance and sustainability before Lululemon figures it out."

MEDIA RECOMMENDATION:
Where should they show up and when? End with one tactical move competitors will miss.
Example: "Tactical move: Dominate LinkedIn Sunday nights when B2B decision-makers scroll guilt-free."

CREATIVE RECOMMENDATION:
What tone, angle, or hook fits this moment? End with a campaign thought-starter.
Example: "Consider: 'Comfort is the new performance.'"

Be bold and specific. Reference the actual data.'''

new_text = '''Create a brief using the Cultural Momentum Matrix (CMM)™ structure:

## 1. WHERE TO PLAY: Cultural Territory Mapping

Analyze the data and identify:
- **Hot Zones**: Dominant topics (>10K mentions) — lead with authority, expect competition
- **Active Zones**: Growing topics (2K-10K mentions) — engage strategically, build expertise  
- **Opportunity Zones**: Emerging topics (<2K mentions) — early mover advantage, test and learn
- **Avoid Zones**: High conflict, high risk topics to steer clear of

End with: "Territory Recommendation: [specific territory] because [data-backed reason]"

## 2. WHEN TO MOVE: Momentum Timing

Based on the current Mood Score, identify the timing zone:
- **Strike Zone (60-80)**: Optimal engagement window — audiences receptive but not oversaturated. Recommendation: ENGAGE NOW
- **Caution Zone (40-59)**: Wait for positive shift or proceed with extra sensitivity
- **Storm Zone (<40)**: Defensive positioning only
- **Peak Zone (80+)**: High competition, premium content required

Factor in Velocity (how fast topics are moving) and Longevity (how long they'll last).

End with: "Timing Recommendation: [ENGAGE NOW / WAIT / PROCEED WITH CAUTION] because [data-backed reason]"

## 3. WHAT TO SAY: Message Architecture

Based on the empathy score and emotional climate:
- **Empathy Calibration**: Match message warmth to current cultural mood
- **Tone Recommendation**: Specific guidance on voice and approach
- **Message Hierarchy**: What to lead with, what to support with
- **Creative Thought-Starter**: One campaign idea or hook that fits this moment

End with: "Consider: '[specific campaign thought-starter]'"

Be bold and specific. Reference actual data points. Make decisions, not suggestions.'''

content = content.replace(old_text, new_text)

with open('app.py', 'w') as f:
    f.write(content)

print("✅ Brief structure updated to CMM")
