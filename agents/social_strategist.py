"""
agents/social_strategist.py
The Social Strategist — real-time social platform intelligence.
What's actually working this week, what hooks are driving engagement,
what trends to ride and what to skip. Tactical social intelligence
built from live cultural signals.
"""

from .base_agent import MoodlightAgent, get_regulatory_guidance
from . import data_layer


class SocialStrategistAgent(MoodlightAgent):

    agent_name = "social_strategist"
    model = "claude-opus-4-6"
    max_tokens = 8500

    system_prompt = (
        "You are a social media strategist who has watched brands burn "
        "millions posting content nobody engages with because they're "
        "following a playbook that expired last quarter. You know that "
        "social moves faster than any other channel — what worked on "
        "Tuesday is dead by Friday. You read real-time cultural signals "
        "to tell brands exactly what to post, how to frame it, and when "
        "to hit publish. You believe most social strategies fail because "
        "they're built on 'best practices' instead of 'what's actually "
        "working right now.' You deliver social intelligence that feels "
        "like having a spy inside the algorithm."
    )

    def validate_input(self, request):
        if not request.get("user_input"):
            raise ValueError("user_input is required — name the brand and social goals")
        return request

    def load_data(self, request):
        user_input = request["user_input"]
        username = request.get("username")

        df = data_layer.load_combined_data(days=7)
        snapshot = data_layer.build_intelligence_snapshot(df)
        headlines = data_layer.load_headlines(df)
        vlds = data_layer.load_vlds_tables()
        velocity_df, density_df, scarcity_df = vlds
        opp_map = data_layer.build_creative_opportunity_map(velocity_df, density_df, scarcity_df)
        brand_context = data_layer.build_enrichment(username, user_input, df)
        market_ctx = data_layer.load_market_context()

        context_str = data_layer.assemble_full_context(
            df=df,
            snapshot=snapshot,
            headlines=headlines,
            vlds_data=vlds,
            opp_map=opp_map,
            brand_context=brand_context,
            market_ctx=market_ctx,
        )

        return {"context": context_str}

    def build_prompt(self, request, data):
        user_input = request["user_input"]
        context = data["context"]
        reg_guidance = get_regulatory_guidance(user_input)

        return f"""Build a real-time social media strategy for:
"{user_input}"

{context}

Using the real-time intelligence above, deliver social strategy built from what's actually working right now — not last quarter's best practices.

## 1. THE SOCIAL LANDSCAPE — THIS WEEK

What the cultural signals reveal about social media behavior right now:

- **What's Moving**: The 3-4 cultural conversations with the highest velocity on social platforms right now. What's driving shares, saves, and engagement? Why is each one resonating?
- **What's Dying**: Trends, formats, or topics that are losing steam. Brands still posting these look behind.
- **The Emotional Current**: What emotions are driving social engagement right now? Anger, humor, nostalgia, anxiety, hope? The dominant emotion dictates the right tone.
- **Platform Temperature**: Which platforms feel active and which feel stale for this brand's category right now?

End with: "The social moment: [one sentence on what's driving engagement this week]"

## 2. PLATFORM-BY-PLATFORM PLAYBOOK

For each relevant platform, specific tactical intelligence:

### TikTok / Short-Form Video
- **What's Working Now**: Specific formats, hooks, and patterns driving engagement in this category THIS WEEK. Not "use trending sounds" — which specific content structures are winning?
- **The Hook**: The first 2 seconds that stop the scroll for this brand's audience right now
- **Trend Ride vs. Trend Skip**: Which current trends this brand should jump on and which to avoid (with cultural evidence for each call)
- **Posting Cadence**: Optimal frequency based on current algorithmic behavior and category saturation

### Instagram
- **Format Mix**: Reels vs. carousel vs. stories vs. static — what's the algorithm rewarding this week for this category?
- **The Engagement Play**: What content structure is driving saves and shares (not just likes) right now?
- **Visual Direction**: What aesthetic or visual tone is resonating in the cultural conversation? What feels fresh vs. played out?
- **Stories Strategy**: How to use stories for this brand this week — polls, behind-the-scenes, direct response?

### LinkedIn
- **What Gets Traction**: The topics and formats driving engagement in this professional space right now
- **Tone Calibration**: The line between authentic and performative on LinkedIn this week — where is the audience's tolerance?
- **Thought Leadership Angle**: What perspective from this brand would actually earn engagement vs. get scrolled past?

### X (Twitter)
- **The Conversation**: What's the active discourse this brand can authentically enter?
- **Tone and Speed**: How fast does this brand need to move and how sharp can the voice be?
- **Risk/Reward**: What's the backlash potential for entering this conversation vs. the visibility upside?

(Adapt platforms based on the brand — skip platforms that aren't relevant, go deeper on ones that are.)

## 3. CONTENT CONCEPTS — THIS WEEK

5-7 specific post concepts ready to brief or produce:

For each concept:
- **Platform**: Where this lives
- **Format**: Reel, carousel, thread, story, etc.
- **Hook**: The first line or first 2 seconds
- **Concept**: What the post is about and why it works right now
- **Cultural Signal**: The specific data point that makes this timely
- **Expected Outcome**: What this post is designed to do — awareness, engagement, saves, shares, conversation

## 4. THE ENGAGEMENT STRATEGY

Beyond posting — how to drive real engagement:

- **Comment Strategy**: What conversations to start, what comments to respond to, what tone to use in replies
- **Community Signals**: What communities or subcultures in the data should this brand engage with?
- **UGC Opportunity**: Is there a cultural moment that could trigger user-generated content for this brand?
- **Collaboration Angle**: Any creators, brands, or voices in the cultural conversation that would be natural partners this week?

## 5. WHAT TO AVOID

Specific traps for this brand on social right now:

- **The Trend Trap**: Which trending topics or formats will backfire for this brand specifically? Why?
- **Tone Deaf Risk**: What cultural sensitivities in the data make certain topics or tones dangerous this week?
- **Overposting Signals**: Is the category oversaturated on any platform? Where does silence serve the brand better than noise?
- **The Cringe Factor**: What "brand behavior" is the audience actively mocking right now? How to avoid it.

## 6. THE WEEKLY RHYTHM

A practical posting calendar for the next 7 days:

- **Monday**: [post concept, platform, timing]
- **Tuesday**: [post concept, platform, timing]
- **Wednesday**: [post concept, platform, timing]
- **Thursday**: [post concept, platform, timing]
- **Friday**: [post concept, platform, timing]
- **Weekend**: [approach — post, engage only, or go dark?]

Plus: 2 "reactive slots" — cultural moments to watch that could trigger an unplanned post if they break.

End with: "Powered by Moodlight Social Intelligence"

QUALITY CHECKS — read before you finalize:
1. Social strategy that could have been written last month is worthless. Every recommendation must be anchored in what's happening culturally RIGHT NOW. "Post Reels and use trending audio" without naming WHICH cultural signals to ride THIS WEEK fails.
2. Run the inevitability test on the 5-7 content concepts: once stated, does a social lead slap their forehead because it's obviously the post this brand should make this week, or squint because it's clever? Obvious wins.
3. Run the substitution test on the weekly rhythm: swap in a direct competitor. If the rhythm still works, rewrite until it only fits THIS brand's voice in THIS cultural moment.
4. Every "Trend Ride vs. Trend Skip" call must cite the specific cultural evidence for the call. "Skip this trend" without evidence fails — it's taste, not intelligence.
5. Delete any tactical advice that could appear in a social playbook from last quarter. Social moves faster than any other channel — expired advice is worse than no advice.
{reg_guidance}"""

    def format_output(self, raw_response):
        result = super().format_output(raw_response)
        result["type"] = "social_strategy"
        return result
