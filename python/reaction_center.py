class ReactionCenter:
    def __init__(self, personality="DEFAULT"):
        self.personality = personality
        
        # position, delay,  velocity,time
        self.EMOTIONS = {
            "NEUTRAL": { "mouth": "M:0,35,0,35,0,35", "eyes": "E:0,35,0,35", "bars": "B:0,0,0,0,0,0,0,0", "curtain": "C:10,10" },

            "HAPPY_1": { "mouth": "M:-30,20,30,20,-40,20", "eyes": "E:5,20,15,20", "bars": "B:0,1500,20,1500,-20,1500,0,1500" },
            "HAPPY_2": { "mouth": "M:-55,20,55,20,-40,20", "eyes": "E:10,20,20,20", "bars": "B:5,1500,35,1500,-35,1500,-5,1500" },
            "HAPPY_3": { "mouth": "M:-90,10,90,10,10,10", "eyes": "E:15,10,30,10", "bars": "B:10,1500,50,1500,-50,1500,-10,1500" },

            "SAD_1": { "mouth": "M:35,30,-35,30,0,30", "eyes": "E:-10,30,-30,30", "bars": "B:0,1500,-20,1500,20,1500,0,1500"  },
            "SAD_2": { "mouth": "M:55,30,-55,30,-30,30", "eyes": "E:-15,30,-55,30", "bars": "B:0,1500,-35,1500,35,1500,0,1500"  },
            "SAD_3": { "mouth": "M:80,15,-80,15,-80,15", "eyes": "E:-25,15,-75,15", "bars": "B:0,1500,-50,1500,50,1500,0,1500" },

            "ANGRY_1": { "mouth": "M:0,5,0,5,-40,5", "eyes": "E:0,5,0,5", "bars": "B:-20,1500,-10,1500,-10,1500,10,1500" },
            "ANGRY_2": { "mouth": "M:0,5,0,5,-40,5", "eyes": "E:0,5,0,5", "bars": "B:-35,1500,-10,1500,-10,1500,10,1500" }, 
            "ANGRY_3": { "mouth": "M:0,5,0,5,-40,5", "eyes": "E:0,5,0,5", "bars": "B:-50,1500,-10,1500,-10,1500,10,1500" }, 

            "SURPRISE_1": { "mouth": "M:-10,5,10,5,-60,5", "eyes": "E:0,5,15,5", "bars": "B:0,1500,0,1500,0,1500,10,1500" },
            "SURPRISE_2": { "mouth": "M:-10,5,10,5,-90,5", "eyes": "E:0,5,15,5", "bars": "B:0,1500,-30,1500,-30,1500,20,1500" },  
            "SURPRISE_3": { "mouth": "M:-10,5,10,5,-90,5", "eyes": "E:0,5,15,5", "bars": "B:0,1500,30,1500,30,1500,-20,1500" }, 

            "FEAR_1": { "mouth": "M:0,15,0,15,-20,15", "eyes": "E:30,15,-20,15", "bars": "B:0,1500,-10,1500,-10,1500,20,1500" },
            "FEAR_2": { "mouth": "M:0,15,0,15,-40,15", "eyes": "E:60,15,-20,15", "bars": "B:0,1500,-10,1500,-10,1500,35,1500" },
            "FEAR_3": { "mouth": "M:0,15,0,15,-40,15", "eyes": "E:90,10,-40,10", "bars": "B:-10,1500,-20,1500,-20,1500,50,1500" },

            "DISGUST_1": { "mouth": "M:-5,5,15,5,-5,5", "eyes": "E:-90,5,80,5", "bars": "B:0,1500,-20,1500,-20,1500,0,1500" },  
            "DISGUST_2": { "mouth": "M:-15,5,-5,5,-15,5", "eyes": "E:-20,5,80,5", "bars": "B:0,1500,-20,1500,-20,1500,0,1500" },
            "DISGUST_3": { "mouth": "M:-20,5,-10,5,-20,5", "eyes": "E:30,5,70,5", "bars": "B:0,1500,-20,1500,-20,1500,0,1500" },

            "CAUTIOUS_1": { "mouth": "M:0,10,0,10,-30,10", "eyes": "E:80,10,10,10", "bars": "B:0,0,0,0,0,0,10,1500" }, 
            "CAUTIOUS_2": { "mouth": "M:0,10,0,10,-30,10", "eyes": "E:-10,10,-10,10", "bars": "B:0,0,0,0,0,0,0,0" },
            "CAUTIOUS_3": { "mouth": "M:0,10,0,10,0,10", "eyes": "E:-80,10,-30,10", "bars": "B:0,0,0,0,0,0,0,0" },

            "APPRECIATION_1": { "mouth": "M:-50,10,50,10,0,10", "eyes": "E:10,10,-40,10", "bars": "B:0,1500,-20,1500,-20,1500,0,1500" }, 
            "APPRECIATION_2": { "mouth": "M:-50,10,50,10,0,10", "eyes": "E:20,10,0,10", "bars": "B:0,1500,-20,1500,-20,1500,0,1500"},
            "APPRECIATION_3": { "mouth": "M:-50,10,50,10,0,10", "eyes": "E:20,10,-40,10", "bars": "B:0,1500,-20,1500,-20,1500,0,1500" },

            "ANTICIPATION_1": { "mouth": "M:-30,5,-30,5,0,5", "eyes": "E:40,5,20,5", "bars": "B:0,1500,-20,1500,-20,1500,0,1500" }, 
            "ANTICIPATION_2": { "mouth": "M:-30,5,-30,5,0,5", "eyes": "E:0,5,20,5", "bars": "B:0,1500,-20,1500,-20,1500,0,1500" },
            "ANTICIPATION_3": { "mouth": "M:-30,5,-30,5,0,5", "eyes": "E:-40,5,10,5", "bars": "B:0,1500,-20,1500,-20,1500,0,1500" },

            "TRUST_1": { "curtain": "C:0,10", "bars": "B:0,1500,10,500,0,1500,0,1500" },
            "TRUST_2": { "curtain": "C:50,5000", "bars": "B:-10,1500,-20,1500,-10,1500,10,1500"},
            "TRUST_3": { "curtain": "C:50,7000", "bars": "B:-10,1500,-30,1500,-10,1500,10,1500" },
            
            "DISTRUST_1": { "curtain": "C:0,10", "bars": "B:0,1500,0,1500,0,1500,0,1500" },
            "DISTRUST_2": { "curtain": "C:-50,5000", "bars": "B:10,1500,20,1500,10,1500,-10,1500" },
            "DISTRUST_3": { "curtain": "C:-50,7000", "bars": "B:20,1500,40,1500,20,1500,-10,1500" }
        }

    """
    def get_reaction(self, trigger, emotion="NEUTRAL", distance=100.0, mood="NEUTRAL"):
       
      #lculates intensity and maps the trigger to a physical output.
        target_level = "NEUTRAL"
        audio_file = None
        
        # 1. CALCULATE INTENSITY
        intensity = 1
        if distance < 40.0: intensity = 3
        elif distance < 80.0: intensity = 2

        # 2. TRIGGER ROUTING
        if trigger == "OBSTACLE_CLOSE":
            target_level = "SURPRISE_3"
            
        elif trigger == "LOUD_NOISE":
            target_level = "SURPRISE_3"
            audio_file = r"media/jetson/sd/beedel/bidel/sound/swanlake.mp3"
            
        elif trigger == "LONG_NOISE":
            target_level = "APPRECIATION_3"
            
        elif trigger == "PERSON_LEFT":
            if mood == "LONELY": target_level = "SAD_2"
            else: target_level = "NEUTRAL"
            
        elif trigger == "INVESTIGATING":
            target_level = "CAUTIOUS_1"
            
        elif trigger == "PATROLLING":
            target_level = "NEUTRAL"
            
        elif trigger == "EMOTION_STABLE":
            if emotion == "HAPPY": target_level = f"HAPPY_{intensity}"
            elif emotion == "SAD": target_level = f"SAD_{intensity}"
            elif emotion == "ANGRY":
                # Apply Personality Filter!
                if self.personality == "SHY": target_level = f"FEAR_{intensity}"
                else: target_level = f"ANGRY_{intensity}"
            elif emotion == "SURPRISE": target_level = f"SURPRISE_{intensity}"
            elif emotion == "FEAR": target_level = f"FEAR_{intensity}"
            elif emotion == "DISGUST": target_level = f"DISGUST_{intensity}"

        # 3. FALLBACK AND PACKAGING
        if target_level not in self.EMOTIONS:
            target_level = "NEUTRAL"
    
        """
    def get_reaction(self, emotion_key):
        print(f"[REACTION CENTER] RETURNING: {emotion_key}")

        return self.EMOTIONS.get( emotion_key,self.EMOTIONS["NEUTRAL"] )