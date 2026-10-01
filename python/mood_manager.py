import json
import math
import os
import time


class MoodManager:
    """
    Three-layer affect manager:

    1. initial_mood:
       The user-selected VAD resting point.

    2. current_mood:
       A persistent VAD state changed by emotional events.

    3. transient emotion:
       A stronger temporary emotion that gradually fades,
       revealing the updated current mood underneath it.

    Personality affects:
    - how strongly events update the current mood;
    - how quickly temporary emotions fade;
    - how slowly the current mood returns to the initial mood.
    """

    # =============================================================
    # VAD REPRESENTATION OF EMOTIONS
    # =============================================================
    EMOTION_VAD = {
        "NEUTRAL": (
            0.00,
            0.00,
            0.00
        ),

        "HAPPY": (
            0.80,
            0.55,
            0.30
        ),

        "SAD": (
            -0.70,
            -0.40,
            -0.45
        ),

        "ANGRY": (
            -0.75,
            0.80,
            0.65
        ),

        "SURPRISE": (
            0.00,
            0.90,
            0.00
        ),

        "FEAR": (
            -0.80,
            0.80,
            -0.70
        ),

        "DISGUST": (
            -0.65,
            0.35,
            0.30
        ),

        "CAUTIOUS": (
            -0.20,
            0.40,
            -0.20
        ),

        "APPRECIATION": (
            0.65,
            0.30,
            0.20
        ),

        "ANTICIPATION": (
            0.45,
            0.65,
            0.20
        ),

        "TRUST": (
            0.70,
            0.25,
            0.40
        ),

        "DISTRUST": (
            -0.60,
            0.45,
            -0.40
        )
    }

    # =============================================================
    # INITIAL STRENGTH OF EACH EXPRESSION LEVEL
    # =============================================================
    LEVEL_STRENGTH = {
        1: 0.34,
        2: 0.62,
        3: 1.00
    }

    # =============================================================
    # HOW STRONGLY AN EVENT UPDATES THE PERSISTENT CURRENT MOOD
    #
    # Higher emotional levels must have a stronger lasting effect.
    # =============================================================
    LEVEL_MOOD_IMPACT = {
        1: 0.22,
        2: 0.38,
        3: 0.60
    }

    # =============================================================
    # BASE TRANSIENT DECAY SPEED PER SECOND
    # =============================================================
    BASE_DECAY_RATE = {
        "HAPPY": 0.14,
        "SAD": 0.10,
        "ANGRY": 0.16,
        "SURPRISE": 0.28,
        "FEAR": 0.13,
        "DISGUST": 0.13,
        "CAUTIOUS": 0.14,
        "APPRECIATION": 0.12,
        "ANTICIPATION": 0.16,
        "TRUST": 0.08,
        "DISTRUST": 0.09
    }

    # Global tuning value for transient duration.
    #
    # Smaller value = emotion lasts longer.
    # Larger value = emotion disappears faster.
    #
    # Recommended range:
    # 0.35 = very slow
    # 0.55 = moderately slow
    # 0.75 = slightly slow
    # 1.00 = original speed
    TRANSIENT_DECAY_MULTIPLIER = 0.55

    # Current mood does not return toward initial mood until this
    # many seconds have passed without an emotional event.
    INACTIVITY_DELAY = 60.0

    # The persistent mood expression can reach level 2 when the
    # current mood has a sufficiently large VAD magnitude.
    MOOD_LEVEL_2_MAGNITUDE = 0.90

    # Small moods below this magnitude are shown as neutral.
    NEUTRAL_MAGNITUDE_THRESHOLD = 0.20

    POSITIVE_EMOTIONS = {
        "HAPPY",
        "APPRECIATION",
        "ANTICIPATION",
        "TRUST"
    }

    NEGATIVE_EMOTIONS = {
        "SAD",
        "ANGRY",
        "FEAR",
        "DISGUST",
        "CAUTIOUS",
        "DISTRUST"
    }

    def __init__(
        self,
        personality_name="BUBBLY",
        initial_mood=None,
        personality_file="personality.json"
    ):
        if initial_mood is None:
            initial_mood = {
                "valence": 0.0,
                "arousal": 0.0,
                "dominance": 0.0
            }

        self.personality_name = personality_name

        self.personality = self._load_personality(
            personality_name,
            personality_file
        )

        # =========================================================
        # INITIAL MOOD
        # =========================================================
        self.initial_mood = {
            "valence": self._clamp(
                float(
                    initial_mood.get(
                        "valence",
                        0.0
                    )
                )
            ),

            "arousal": self._clamp(
                float(
                    initial_mood.get(
                        "arousal",
                        0.0
                    )
                )
            ),

            "dominance": self._clamp(
                float(
                    initial_mood.get(
                        "dominance",
                        0.0
                    )
                )
            )
        }

        # Mood begins at the selected initial mood.
        # This is only assigned once.
        self.current_mood = (
            self.initial_mood.copy()
        )

        # =========================================================
        # TEMPORARY EMOTION
        # =========================================================
        self.transient_family = None

        self.transient_vad = (
            0.0,
            0.0,
            0.0
        )

        self.transient_strength = 0.0
        self.transient_decay_rate = 0.0

        self.last_event_time = time.time()

        self.inactivity_delay = (
            self.INACTIVITY_DELAY
        )

        # =========================================================
        # INACTIVITY RECOVERY
        #
        # Higher neuroticism makes emotional experiences influence
        # mood for longer.
        #
        # This is intentionally much slower than the previous value.
        # =========================================================
        neuroticism = self.personality[
            "neuroticism"
        ]

        self.inactivity_return_rate = (
            0.0005
            + 0.0005
            * (1.0 - neuroticism)
        )

        print(
            f"[MOOD] Personality: "
            f"{self.personality_name}"
        )

        print(
            "[MOOD] Initial VAD: "
            f"V={self.initial_mood['valence']:.2f}, "
            f"A={self.initial_mood['arousal']:.2f}, "
            f"D={self.initial_mood['dominance']:.2f}"
        )

        print(
            "[MOOD] Inactivity delay: "
            f"{self.inactivity_delay:.1f}s"
        )

        print(
            "[MOOD] Inactivity recovery rate: "
            f"{self.inactivity_return_rate:.6f}/s "
        )

        print(
            "[MOOD] Transient decay multiplier: "
            f"{self.TRANSIENT_DECAY_MULTIPLIER:.2f}"
        )

    # =============================================================
    # GENERAL FUNCTIONS
    # =============================================================
    @staticmethod
    def _clamp(
        value,
        minimum=-1.0,
        maximum=1.0
    ):
        return max(
            minimum,
            min(
                maximum,
                value
            )
        )

    def _load_personality(
        self,
        personality_name,
        personality_file
    ):
        """
        Loads one personality from the personality JSON file.
        """

        if not os.path.isabs(
            personality_file
        ):
            file_directory = os.path.dirname(
                os.path.abspath(__file__)
            )

            personality_file = os.path.join(
                file_directory,
                personality_file
            )

        with open(
            personality_file,
            "r",
            encoding="utf-8"
        ) as file:
            personalities = json.load(
                file
            )

        if personality_name not in personalities:
            raise ValueError(
                f"Personality '{personality_name}' "
                f"was not found in {personality_file}"
            )

        personality = personalities[
            personality_name
        ]

        required_traits = [
            "openness",
            "conscientiousness",
            "extraversion",
            "agreeableness",
            "neuroticism"
        ]

        for trait in required_traits:
            if trait not in personality:
                raise ValueError(
                    f"Personality '{personality_name}' "
                    f"is missing the trait '{trait}'"
                )

        return {
            trait: self._clamp(
                float(
                    personality[trait]
                ),
                0.0,
                1.0
            )
            for trait in required_traits
        }

    @staticmethod
    def _split_emotion_key(
        emotion_key
    ):
        """
        Converts:

            HAPPY_3 -> HAPPY, 3
            FEAR_2 -> FEAR, 2
            NEUTRAL -> NEUTRAL, 1
        """

        emotion_key = str(
            emotion_key
        ).upper()

        if emotion_key == "NEUTRAL":
            return (
                "NEUTRAL",
                1
            )

        parts = emotion_key.rsplit(
            "_",
            1
        )

        if (
            len(parts) == 2
            and parts[1].isdigit()
        ):
            family = parts[0]

            level = max(
                1,
                min(
                    3,
                    int(parts[1])
                )
            )

            return (
                family,
                level
            )

        return (
            emotion_key,
            1
        )

    # =============================================================
    # PERSONALITY EFFECT ON MOOD CHANGE
    # =============================================================
    def _personality_sensitivity(
        self,
        family
    ):
        openness = self.personality[
            "openness"
        ]

        conscientiousness = self.personality[
            "conscientiousness"
        ]

        extraversion = self.personality[
            "extraversion"
        ]

        agreeableness = self.personality[
            "agreeableness"
        ]

        neuroticism = self.personality[
            "neuroticism"
        ]

        if family in self.POSITIVE_EMOTIONS:
            # Extraverted and agreeable personalities are affected
            # more strongly by positive social events.
            sensitivity = (
                0.50
                + 0.25 * extraversion
                + 0.25 * agreeableness
            )

        elif family == "SURPRISE":
            # Open and neurotic personalities react more strongly
            # to unexpected events.
            sensitivity = (
                0.50
                + 0.25 * openness
                + 0.25 * neuroticism
            )

        elif family in self.NEGATIVE_EMOTIONS:
            # Neurotic personalities are affected more strongly by
            # negative events.
            sensitivity = (
                0.50
                + 0.35 * neuroticism
                + 0.15
                * (1.0 - agreeableness)
            )

        else:
            sensitivity = 0.75

        # High conscientiousness makes mood less volatile.
        sensitivity *= (
            1.10
            - 0.20 * conscientiousness
        )

        return self._clamp(
            sensitivity,
            0.35,
            1.20
        )

    # =============================================================
    # PERSONALITY EFFECT ON TRANSIENT EMOTION DECAY
    # =============================================================
    def _calculate_decay_rate(
        self,
        family
    ):
        rate = self.BASE_DECAY_RATE.get(
            family,
            0.14
        )

        conscientiousness = self.personality[
            "conscientiousness"
        ]

        extraversion = self.personality[
            "extraversion"
        ]

        neuroticism = self.personality[
            "neuroticism"
        ]

        if family in self.NEGATIVE_EMOTIONS:
            # Higher neuroticism makes negative emotions last
            # longer.
            rate *= (
                1.10
                - 0.50 * neuroticism
            )

        elif family in self.POSITIVE_EMOTIONS:
            # Higher extraversion slightly prolongs positive
            # emotions.
            rate *= (
                1.05
                - 0.25 * extraversion
            )

        # Higher conscientiousness creates slower and smoother
        # emotional transitions.
        rate *= (
            1.05
            - 0.20 * conscientiousness
        )

        # Global tuning adjustment.
        rate *= (
            self.TRANSIENT_DECAY_MULTIPLIER
        )

        return self._clamp(
            rate,
            0.02,
            0.35
        )

    # =============================================================
    # RECEIVE A NEW EMOTIONAL EVENT
    # =============================================================
    def receive_emotion(
        self,
        emotion_key
    ):
        """
        Called once when the brain creates a new emotional event.

        First:
            The event updates the persistent current mood.

        Then:
            The temporary visible emotion begins.
        """

        (
            family,
            level
        ) = self._split_emotion_key(
            emotion_key
        )

        if family == "NEUTRAL":
            return False

        if family not in self.EMOTION_VAD:
            print(
                f"[MOOD] Unknown emotion: "
                f"{emotion_key}"
            )

            return False

        event_vad = self.EMOTION_VAD[
            family
        ]

        sensitivity = (
            self._personality_sensitivity(
                family
            )
        )

        mood_impact = (
            self.LEVEL_MOOD_IMPACT[level]
            * sensitivity
        )

        # Prevent an unusually sensitive personality from making
        # one event completely overwrite the current mood.
        mood_impact = self._clamp(
            mood_impact,
            0.0,
            0.75
        )

        mood_keys = (
            "valence",
            "arousal",
            "dominance"
        )

        old_mood = (
            self.current_mood.copy()
        )

        # Move current mood toward the emotional event.
        for index, key in enumerate(
            mood_keys
        ):
            self.current_mood[key] += (
                event_vad[index]
                - self.current_mood[key]
            ) * mood_impact

            self.current_mood[key] = (
                self._clamp(
                    self.current_mood[key]
                )
            )

        # Start or replace the temporary emotion.
        self.transient_family = family
        self.transient_vad = event_vad

        self.transient_strength = (
            self.LEVEL_STRENGTH[level]
        )

        self.transient_decay_rate = (
            self._calculate_decay_rate(
                family
            )
        )

        self.last_event_time = time.time()

        print(
            f"[MOOD] Event {emotion_key} | "
            f"Impact={mood_impact:.3f}"
        )

        print(
            "[MOOD] Previous mood: "
            f"V={old_mood['valence']:.2f}, "
            f"A={old_mood['arousal']:.2f}, "
            f"D={old_mood['dominance']:.2f}"
        )

        print(
            "[MOOD] Updated mood:  "
            f"V={self.current_mood['valence']:.2f}, "
            f"A={self.current_mood['arousal']:.2f}, "
            f"D={self.current_mood['dominance']:.2f}"
        )

        print(
            "[MOOD] Transient: "
            f"{self.transient_family} | "
            f"Strength={self.transient_strength:.2f} | "
            f"Decay={self.transient_decay_rate:.3f}/s"
        )

        return True

    # =============================================================
    # CONTINUOUS UPDATE
    # =============================================================
    def update(
        self,
        delta_time,
        inactive=False
    ):
        """
        Called every brain loop.

        1. The temporary emotion continuously fades toward the
           updated current mood.

        2. After prolonged inactivity, the current mood very slowly
           returns toward the selected initial mood.
        """

        delta_time = self._clamp(
            float(delta_time),
            0.0,
            1.0
        )

        # ---------------------------------------------------------
        # Temporary emotion decay
        # ---------------------------------------------------------
        if self.transient_strength > 0.0:
            self.transient_strength -= (
                self.transient_decay_rate
                * delta_time
            )

            self.transient_strength = max(
                0.0,
                self.transient_strength
            )

            if self.transient_strength <= 0.0:
                self.transient_strength = 0.0
                self.transient_family = None

                self.transient_vad = (
                    0.0,
                    0.0,
                    0.0
                )

        # ---------------------------------------------------------
        # Slow mood recovery during inactivity
        # ---------------------------------------------------------
        inactive_long_enough = (
            inactive
            and (
                time.time()
                - self.last_event_time
                >= self.inactivity_delay
            )
        )

        if inactive_long_enough:
            step = min(
                1.0,
                self.inactivity_return_rate
                * delta_time
            )

            for key in (
                "valence",
                "arousal",
                "dominance"
            ):
                self.current_mood[key] += (
                    self.initial_mood[key]
                    - self.current_mood[key]
                ) * step

                self.current_mood[key] = (
                    self._clamp(
                        self.current_mood[key]
                    )
                )

    # =============================================================
    # BLEND TEMPORARY EMOTION WITH CURRENT MOOD
    # =============================================================
    def get_display_vad(self):
        """
        transient_strength = 1:
            The display is almost completely the temporary emotion.

        transient_strength = 0:
            The display is the persistent current mood.
        """

        strength = self._clamp(
            self.transient_strength,
            0.0,
            1.0
        )

        mood_values = (
            self.current_mood["valence"],
            self.current_mood["arousal"],
            self.current_mood["dominance"]
        )

        return tuple(
            mood_values[index]
            + strength
            * (
                self.transient_vad[index]
                - mood_values[index]
            )
            for index in range(3)
        )

    # =============================================================
    # CONVERT UPDATED MOOD VAD TO A DISCRETE EXPRESSION
    # =============================================================
    def _vad_to_mild_expression(
        self,
        vad
    ):
        """
        Converts the updated persistent mood to a visible expression.

        Unlike the previous version, the current mood can produce
        level 1 or level 2 expressions. This allows the robot to
        settle into a visibly different state after an emotion.

        Level 3 expressions are still reserved for strong temporary
        emotional events.
        """

        (
            valence,
            arousal,
            dominance
        ) = vad

        magnitude = math.sqrt(
            valence ** 2
            + arousal ** 2
            + dominance ** 2
        )

        if (
            magnitude
            < self.NEUTRAL_MAGNITUDE_THRESHOLD
        ):
            return "NEUTRAL"

        level = (
            2
            if magnitude
            >= self.MOOD_LEVEL_2_MAGNITUDE
            else 1
        )

        # ---------------------------------------------------------
        # Positive mood
        # ---------------------------------------------------------
        if valence >= 0.32:
            if arousal >= 0.62:
                return (
                    f"ANTICIPATION_{level}"
                )

            return (
                f"HAPPY_{level}"
            )

        # ---------------------------------------------------------
        # Negative mood
        # ---------------------------------------------------------
        if valence <= -0.32:
            if (
                arousal <= 0.05
            ):
                return (
                    f"SAD_{level}"
                )

            if (
                dominance <= -0.20
            ):
                return (
                    f"FEAR_{level}"
                )

            if (
                dominance >= 0.25
                and arousal >= 0.45
            ):
                return (
                    f"ANGRY_{level}"
                )

            return (
                f"CAUTIOUS_{level}"
            )

        # ---------------------------------------------------------
        # Valence is close to neutral
        # ---------------------------------------------------------
        if arousal >= 0.58:
            if dominance < -0.10:
                return (
                    f"CAUTIOUS_{level}"
                )

            if valence >= 0.0:
                return (
                    f"ANTICIPATION_{level}"
                )

            return (
                f"CAUTIOUS_{level}"
            )

        # Slightly negative low-arousal mood.
        if (
            valence < -0.10
            and arousal < 0.20
        ):
            return (
                f"SAD_{level}"
            )

        # Slightly positive mood.
        if valence > 0.10:
            return (
                f"HAPPY_{level}"
            )

        return "NEUTRAL"

    # =============================================================
    # GET CURRENT DISCRETE EXPRESSION
    # =============================================================
    def get_expression(self):
        """
        There is no fixed hold duration.

        A strong temporary emotion naturally changes through:

            level 3
            level 2
            level 1
            updated current mood expression
        """

        if self.transient_family is not None:
            if self.transient_strength >= 0.78:
                return (
                    f"{self.transient_family}_3"
                )

            if self.transient_strength >= 0.48:
                return (
                    f"{self.transient_family}_2"
                )

            if self.transient_strength >= 0.16:
                return (
                    f"{self.transient_family}_1"
                )

        # At low transient strength, use the blended VAD.
        # This creates a gradual transition toward the newly updated
        # current mood rather than directly returning to the original
        # initial mood expression.
        return self._vad_to_mild_expression(
            self.get_display_vad()
        )

    # =============================================================
    # INFORMATION FOR BRAIN AND LOGGING
    # =============================================================
    def get_current_mood(self):
        return self.current_mood.copy()

    def get_initial_mood(self):
        return self.initial_mood.copy()

    def get_status(self):
        display_vad = self.get_display_vad()

        return {
            "personality": (
                self.personality_name
            ),

            "mood_valence": (
                self.current_mood["valence"]
            ),

            "mood_arousal": (
                self.current_mood["arousal"]
            ),

            "mood_dominance": (
                self.current_mood["dominance"]
            ),

            "display_valence": (
                display_vad[0]
            ),

            "display_arousal": (
                display_vad[1]
            ),

            "display_dominance": (
                display_vad[2]
            ),

            "transient_emotion": (
                self.transient_family
                or "NONE"
            ),

            "transient_strength": (
                self.transient_strength
            ),

            "transient_decay_rate": (
                self.transient_decay_rate
            ),

            "inactivity_return_rate": (
                self.inactivity_return_rate
            )
        }


"""
import json
import math
import os
import time


class MoodManager:
    
    Simple three-layer affect manager:

    1. initial_mood:
       The user-selected VAD resting point.

    2. current_mood:
       A slow VAD state changed by emotional events.

    3. transient emotion:
       A stronger temporary emotion that continuously fades,
       revealing the updated current mood underneath it.

    Personality does not define the mood destination. It changes:
    - how strongly events update mood;
    - how quickly temporary emotions fade;
    - how quickly mood returns to the initial mood during inactivity.
    

    # =============================================================
    # VAD REPRESENTATION OF EMOTIONS
    # =============================================================
    EMOTION_VAD = {
        "NEUTRAL": (
            0.00,
            0.00,
            0.00
        ),

        "HAPPY": (
            0.80,
            0.55,
            0.30
        ),

        "SAD": (
            -0.70,
            -0.40,
            -0.45
        ),

        "ANGRY": (
            -0.75,
            0.80,
            0.65
        ),

        "SURPRISE": (
            0.00,
            0.90,
            0.00
        ),

        "FEAR": (
            -0.80,
            0.80,
            -0.70
        ),

        "DISGUST": (
            -0.65,
            0.35,
            0.30
        ),

        "CAUTIOUS": (
            -0.20,
            0.40,
            -0.20
        ),

        "APPRECIATION": (
            0.65,
            0.30,
            0.20
        ),

        "ANTICIPATION": (
            0.45,
            0.65,
            0.20
        ),

        "TRUST": (
            0.70,
            0.25,
            0.40
        ),

        "DISTRUST": (
            -0.60,
            0.45,
            -0.40
        )
    }

    # =============================================================
    # INITIAL STRENGTH OF EACH EXPRESSION LEVEL
    # =============================================================
    LEVEL_STRENGTH = {
        1: 0.34,
        2: 0.62,
        3: 1.00
    }

    # =============================================================
    # HOW STRONGLY AN EVENT UPDATES CURRENT MOOD
    # =============================================================
    LEVEL_MOOD_IMPACT = {
        1: 0.16,
        2: 0.22,
        3: 0.20
    }

    # =============================================================
    # BASE CONTINUOUS DECAY SPEED PER SECOND
    # =============================================================
    BASE_DECAY_RATE = {
        "HAPPY": 0.14,
        "SAD": 0.10,
        "ANGRY": 0.16,
        "SURPRISE": 0.28,
        "FEAR": 0.13,
        "DISGUST": 0.13,
        "CAUTIOUS": 0.14,
        "APPRECIATION": 0.12,
        "ANTICIPATION": 0.16,
        "TRUST": 0.08,
        "DISTRUST": 0.09
    }

    POSITIVE_EMOTIONS = {
        "HAPPY",
        "APPRECIATION",
        "ANTICIPATION",
        "TRUST"
    }

    NEGATIVE_EMOTIONS = {
        "SAD",
        "ANGRY",
        "FEAR",
        "DISGUST",
        "CAUTIOUS",
        "DISTRUST"
    }

    def __init__(
        self,
        personality_name='BUBBLY',
        initial_mood=None,
        personality_file="personality.json"
    ):
        if initial_mood is None:
            initial_mood = {
                "valence": 0.0,
                "arousal": 0.0,
                "dominance": 0.0
            }

        self.personality_name = personality_name

        self.personality = self._load_personality(
            personality_name,
            personality_file
        )

        # =========================================================
        # INITIAL MOOD
        # =========================================================
        self.initial_mood = {
            "valence": self._clamp(
                float(
                    initial_mood.get(
                        "valence",
                        0.0
                    )
                )
            ),

            "arousal": self._clamp(
                float(
                    initial_mood.get(
                        "arousal",
                        0.0
                    )
                )
            ),

            "dominance": self._clamp(
                float(
                    initial_mood.get(
                        "dominance",
                        0.0
                    )
                )
            )
        }

        # Mood begins at the user-selected initial mood.
        self.current_mood = (
            self.initial_mood.copy()
        )

        # =========================================================
        # TEMPORARY EMOTION
        # =========================================================
        self.transient_family = None

        self.transient_vad = (
            0.0,
            0.0,
            0.0
        )

        self.transient_strength = 0.0
        self.transient_decay_rate = 0.0

        self.last_event_time = time.time()

        # Mood begins returning toward initial mood only after this
        # amount of inactivity.
        self.inactivity_delay = 30.0

        # Very weak inactivity recovery.
        #
        # High neuroticism causes experiences to influence mood
        # for a longer time.
        neuroticism = self.personality[
            "neuroticism"
        ]

        self.inactivity_return_rate = (
            0.0055
            + 0.0055
            * (1.0 - neuroticism)
        )

        print(
            f"[MOOD] Personality: "
            f"{self.personality_name}"
        )

        print(
            "[MOOD] Initial VAD: "
            f"V={self.initial_mood['valence']:.2f}, "
            f"A={self.initial_mood['arousal']:.2f}, "
            f"D={self.initial_mood['dominance']:.2f}"
        )

        print(
            "[MOOD] Inactivity recovery rate: "
            f"{self.inactivity_return_rate:.4f}"
        )

     =============================================================
     GENERAL FUNCTIONS
     =============================================================
    @staticmethod
    def _clamp(
        value,
        minimum=-1.0,
        maximum=1.0
    ):
        return max(
            minimum,
            min(
                maximum,
                value
            )
        )

    def _load_personality(
        self,
        personality_name,
        personality_file
    ):
        
        Loads one personality from personality.json.
        

        if not os.path.isabs(
            personality_file
        ):
            file_directory = os.path.dirname(
                os.path.abspath(__file__)
            )

            personality_file = os.path.join(
                file_directory,
                personality_file
            )

        with open(
            personality_file,
            "r",
            encoding="utf-8"
        ) as file:
            personalities = json.load(
                file
            )

        if personality_name not in personalities:
            raise ValueError(
                f"Personality '{personality_name}' "
                f"was not found in {personality_file}"
            )

        personality = personalities[
            personality_name
        ]

        required_traits = [
            "openness",
            "conscientiousness",
            "extraversion",
            "agreeableness",
            "neuroticism"
        ]

        for trait in required_traits:
            if trait not in personality:
                raise ValueError(
                    f"Personality '{personality_name}' "
                    f"is missing the trait '{trait}'"
                )

        return {
            trait: self._clamp(
                float(
                    personality[trait]
                ),
                0.0,
                1.0
            )
            for trait in required_traits
        }

    @staticmethod
    def _split_emotion_key(
        emotion_key
    ):
        
        Converts:

            HAPPY_3 -> HAPPY, 3
            FEAR_2 -> FEAR, 2
            NEUTRAL -> NEUTRAL, 1
        

        emotion_key = str(
            emotion_key
        ).upper()

        if emotion_key == "NEUTRAL":
            return (
                "NEUTRAL",
                1
            )

        parts = emotion_key.rsplit(
            "_",
            1
        )

        if (
            len(parts) == 2
            and parts[1].isdigit()
        ):
            family = parts[0]

            level = max(
                1,
                min(
                    3,
                    int(parts[1])
                )
            )

            return (
                family,
                level
            )

        return (
            emotion_key,
            1
        )

    # =============================================================
    # PERSONALITY EFFECT ON MOOD CHANGE
    # =============================================================
    def _personality_sensitivity(
        self,
        family
    ):
        openness = self.personality[
            "openness"
        ]

        conscientiousness = self.personality[
            "conscientiousness"
        ]

        extraversion = self.personality[
            "extraversion"
        ]

        agreeableness = self.personality[
            "agreeableness"
        ]

        neuroticism = self.personality[
            "neuroticism"
        ]

        if family in self.POSITIVE_EMOTIONS:
            # Extraverted and agreeable robots are affected more
            # strongly by positive social events.
            sensitivity = (
                0.50
                + 0.25 * extraversion
                + 0.25 * agreeableness
            )

        elif family == "SURPRISE":
            # Open and neurotic robots react more strongly to
            # unexpected events.
            sensitivity = (
                0.50
                + 0.25 * openness
                + 0.25 * neuroticism
            )

        elif family in self.NEGATIVE_EMOTIONS:
            # Neurotic robots are affected more strongly by
            # negative events.
            sensitivity = (
                0.50
                + 0.35 * neuroticism
                + 0.15
                * (1.0 - agreeableness)
            )

        else:
            sensitivity = 0.75

        # High conscientiousness makes mood less volatile.
        sensitivity *= (
            1.10
            - 0.20 * conscientiousness
        )

        return self._clamp(
            sensitivity,
            0.35,
            1.20
        )

    # =============================================================
    # PERSONALITY EFFECT ON EMOTION DECAY
    # =============================================================
    def _calculate_decay_rate(
        self,
        family
    ):
        rate = self.BASE_DECAY_RATE.get(
            family,
            0.14
        )

        conscientiousness = self.personality[
            "conscientiousness"
        ]

        extraversion = self.personality[
            "extraversion"
        ]

        neuroticism = self.personality[
            "neuroticism"
        ]

        if family in self.NEGATIVE_EMOTIONS:
            # High neuroticism makes negative emotions last longer.
            rate *= (
                1.10
                - 0.50 * neuroticism
            )

        elif family in self.POSITIVE_EMOTIONS:
            # High extraversion slightly prolongs positive emotion.
            rate *= (
                1.05
                - 0.25 * extraversion
            )

        # High conscientiousness creates slower and smoother
        # transitions.
        rate *= (
            1.05
            - 0.20 * conscientiousness
        )

        return self._clamp(
            rate,
            0.04,
            0.35
        )

    # =============================================================
    # RECEIVE A NEW EMOTIONAL EVENT
    # =============================================================
    def receive_emotion(
        self,
        emotion_key
    ):
        
        Called once when the brain creates a new emotional event.

        First:
            The event slightly updates current mood.

        Then:
            The temporary visible emotion begins.
        

        (
            family,
            level
        ) = self._split_emotion_key(
            emotion_key
        )

        if family == "NEUTRAL":
            return False

        if family not in self.EMOTION_VAD:
            print(
                f"[MOOD] Unknown emotion: "
                f"{emotion_key}"
            )

            return False

        event_vad = self.EMOTION_VAD[
            family
        ]

        sensitivity = (
            self._personality_sensitivity(
                family
            )
        )

        mood_impact = (
            self.LEVEL_MOOD_IMPACT[level]
            * sensitivity
        )

        mood_keys = (
            "valence",
            "arousal",
            "dominance"
        )

        # Move current mood slightly toward the event.
        for index, key in enumerate(
            mood_keys
        ):
            self.current_mood[key] += (
                event_vad[index]
                - self.current_mood[key]
            ) * mood_impact

            self.current_mood[key] = (
                self._clamp(
                    self.current_mood[key]
                )
            )

        # Start or replace the temporary emotion.
        self.transient_family = family
        self.transient_vad = event_vad

        self.transient_strength = (
            self.LEVEL_STRENGTH[level]
        )

        self.transient_decay_rate = (
            self._calculate_decay_rate(
                family
            )
        )

        self.last_event_time = time.time()

        print(
            f"[MOOD] Event {emotion_key} | "
            f"Mood VAD: "
            f"V={self.current_mood['valence']:.2f}, "
            f"A={self.current_mood['arousal']:.2f}, "
            f"D={self.current_mood['dominance']:.2f} | "
            f"Decay="
            f"{self.transient_decay_rate:.3f}/s"
        )

        return True

    # =============================================================
    # CONTINUOUS UPDATE
    # =============================================================
    def update(
        self,
        delta_time,
        inactive=False
    ):
        
        Called every brain loop.

        1. Temporary emotion continuously fades toward current mood.

        2. After prolonged inactivity, current mood very slowly
           returns toward the selected initial mood.
        

        delta_time = self._clamp(
            float(delta_time),
            0.0,
            1.0
        )

        # ---------------------------------------------------------
        # Temporary emotion decay
        # ---------------------------------------------------------
        if self.transient_strength > 0.0:
            self.transient_strength -= (
                self.transient_decay_rate
                * delta_time
            )

            self.transient_strength = max(
                0.0,
                self.transient_strength
            )

            if self.transient_strength == 0.0:
                self.transient_family = None

        # ---------------------------------------------------------
        # Weak mood recovery during inactivity
        # ---------------------------------------------------------
        inactive_long_enough = (
            inactive
            and (
                time.time()
                - self.last_event_time
                >= self.inactivity_delay
            )
        )

        if inactive_long_enough:
            step = min(
                1.0,
                self.inactivity_return_rate
                * delta_time
            )

            for key in (
                "valence",
                "arousal",
                "dominance"
            ):
                self.current_mood[key] += (
                    self.initial_mood[key]
                    - self.current_mood[key]
                ) * step

                self.current_mood[key] = (
                    self._clamp(
                        self.current_mood[key]
                    )
                )

    # =============================================================
    # BLEND TEMPORARY EMOTION WITH MOOD
    # =============================================================
    def get_display_vad(self):
        
        transient_strength = 1:
            Display is almost completely the temporary emotion.

        transient_strength = 0:
            Display is current mood.
        

        strength = self._clamp(
            self.transient_strength,
            0.0,
            1.0
        )

        mood_values = (
            self.current_mood["valence"],
            self.current_mood["arousal"],
            self.current_mood["dominance"]
        )

        return tuple(
            mood_values[index]
            + strength
            * (
                self.transient_vad[index]
                - mood_values[index]
            )
            for index in range(3)
        )

    # =============================================================
    # CONVERT LOW-STRENGTH VAD TO A MOOD EXPRESSION
    # =============================================================
    def _vad_to_mild_expression(
        self,
        vad
    ):
        
        Mood only generates level-1 expressions or NEUTRAL.
        Strong expressions come from temporary emotions.
        

        (
            valence,
            arousal,
            dominance
        ) = vad

        magnitude = math.sqrt(
            valence ** 2
            + arousal ** 2
            + dominance ** 2
        )

        if magnitude < 0.24:
            return "NEUTRAL"

        # Positive mood
        if valence > 0.22:
            if arousal > 0.58:
                return "ANTICIPATION_1"

            return "HAPPY_1"

        # Negative mood
        if valence < -0.22:
            if arousal < 0.12:
                return "SAD_1"

            if dominance < -0.12:
                return "FEAR_1"

            if (
                dominance > 0.25
                and arousal > 0.45
            ):
                return "ANGRY_1"

            return "CAUTIOUS_1"

        # Neutral valence but high activation
        if arousal > 0.50:
            return "CAUTIOUS_1"

        return "NEUTRAL"

    # =============================================================
    # GET CURRENT DISCRETE EXPRESSION
    # =============================================================
    def get_expression(self):
        
        There is no fixed hold duration.

        A strong temporary emotion naturally becomes:

            level 3
            level 2
            level 1
            current mood expression
        

        if self.transient_family is not None:

            if self.transient_strength >= 0.78:
                return (
                    f"{self.transient_family}_3"
                )

            if self.transient_strength >= 0.48:
                return (
                    f"{self.transient_family}_2"
                )

            if self.transient_strength >= 0.16:
                return (
                    f"{self.transient_family}_1"
                )

        # At low temporary strength, use the blended VAD.
        # This can create an intermediate neutral or mild state
        # before returning completely to the mood.
        return self._vad_to_mild_expression(
            self.get_display_vad()
        )

    # =============================================================
    # INFORMATION FOR BRAIN/LOGGING
    # =============================================================
    def get_current_mood(self):
        return self.current_mood.copy()

    def get_initial_mood(self):
        return self.initial_mood.copy()

    def get_status(self):
        display_vad = self.get_display_vad()

        return {
            "personality": (
                self.personality_name
            ),

            "mood_valence": (
                self.current_mood["valence"]
            ),

            "mood_arousal": (
                self.current_mood["arousal"]
            ),

            "mood_dominance": (
                self.current_mood["dominance"]
            ),

            "display_valence": (
                display_vad[0]
            ),

            "display_arousal": (
                display_vad[1]
            ),

            "display_dominance": (
                display_vad[2]
            ),

            "transient_emotion": (
                self.transient_family
                or "NONE"
            ),

            "transient_strength": (
                self.transient_strength
            )
        } """