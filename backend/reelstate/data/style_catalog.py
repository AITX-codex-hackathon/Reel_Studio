"""All 100 video shot styles."""
from __future__ import annotations

from ..models.style import VideoStyle

STYLES: list[VideoStyle] = [
    # ── Drone Aerial ──────────────────────────────────────────────────────────
    VideoStyle(
        style_id="VID_DRN_001", category="Drone Aerial", mood="Epic/Grand",
        camera_motion="High-Altitude Orbit", environmental_dynamics="Cloud shadow drift",
        video_prompt="Cinematic high-altitude drone orbit. Camera pitched down 45 degrees, executing a perfect, smooth circle. Massive 3D parallax between roofline and distant horizon. Soft, rolling cloud shadows move actively across the landscape.",
    ),
    VideoStyle(
        style_id="VID_DRN_002", category="Drone Aerial", mood="Dynamic Reveal",
        camera_motion="Low-to-High Pedestal", environmental_dynamics="Tree canopy clearing",
        video_prompt="FPV-style drone reveal. Start low in the foreground tree canopy, execute a rapid, smooth vertical ascent clearing the branches to reveal the estate. Deep parallax shift. Leaves rustle dynamically from downdraft.",
    ),
    VideoStyle(
        style_id="VID_DRN_003", category="Drone Aerial", mood="Calm Luxury",
        camera_motion="Forward Glide", environmental_dynamics="Water surface reflection",
        video_prompt="Low-altitude drone glide over water toward the rear facade. Camera moves perfectly level, 5 feet off the ground. The water surface ripples slightly, catching dynamic specular highlights from the sun.",
    ),
    VideoStyle(
        style_id="VID_DRN_004", category="Drone Aerial", mood="High-Energy",
        camera_motion="Dive to Level-Out", environmental_dynamics="Perspective warp",
        video_prompt="Aggressive drone dive. Start high above the roof, drop rapidly toward the backyard, and execute a buttery-smooth leveling out just above the patio. High kinetic energy, intense perspective shift, realistic edge blur.",
    ),
    VideoStyle(
        style_id="VID_DRN_005", category="Drone Aerial", mood="Moody/Twilight",
        camera_motion="Pull-Back Reveal", environmental_dynamics="Cityscape blooming",
        video_prompt="Slow, sweeping drone pull-back and rise. House is centered, but as camera pulls away, a deep, twinkling cityscape is revealed in the background. Twilight sky gradient transitions seamlessly.",
    ),
    VideoStyle(
        style_id="VID_DRN_006", category="Drone Aerial", mood="Exploration",
        camera_motion="Low Tracking", environmental_dynamics="Grass blowing",
        video_prompt="Drone tracking shot 3 feet above the lawn, moving laterally across the property facade. Long grass and landscaping plants bend and sway realistically in the wind. The house geometry remains perfectly rigid.",
    ),
    VideoStyle(
        style_id="VID_DRN_007", category="Drone Aerial", mood="Dramatic Scale",
        camera_motion="Vertical Drop", environmental_dynamics="Waterfall/Pool dynamics",
        video_prompt="Start looking straight down (top-down view) at the roof. Drone drops vertically down toward the backyard pool. The water ripples and reflects the sky dynamically as the camera approaches the surface.",
    ),
    VideoStyle(
        style_id="VID_DRN_008", category="Drone Aerial", mood="Heroic",
        camera_motion="Fly-Over", environmental_dynamics="Roofline parallax",
        video_prompt="Smooth, level forward flight directly over the peak of the roofline. As the drone crosses the ridge, the expansive backyard and distant landscape are dramatically revealed. Crisp, midday lighting.",
    ),
    VideoStyle(
        style_id="VID_DRN_009", category="Drone Aerial", mood="High-End",
        camera_motion="Reverse Arc", environmental_dynamics="Sunburst",
        video_prompt="Drone flies backward while slowly orbiting the exterior. As the building blocks the sun, a massive, photorealistic anamorphic lens flare bursts and fades dynamically across the lens.",
    ),
    VideoStyle(
        style_id="VID_DRN_010", category="Drone Aerial", mood="Cinematic",
        camera_motion="Spiral Descent", environmental_dynamics="Shadow shifting",
        video_prompt="Drone executes a slow, spiraling descent from 100 feet down to the driveway. Complex 3D spatial calculation; lighting and shadows shift realistically across the exterior walls as the angle changes.",
    ),
    VideoStyle(
        style_id="VID_DRN_011", category="Drone Aerial", mood="Property Boundary",
        camera_motion="High Tracking", environmental_dynamics="Traffic/World life",
        video_prompt="Wide drone tracking shot running parallel to the property line. In the distant background, realistic environmental motion (cars on a road, birds flying) adds kinetic life to the scene without distracting.",
    ),
    VideoStyle(
        style_id="VID_DRN_012", category="Drone Aerial", mood="Tension",
        camera_motion="Push Through Gap", environmental_dynamics="Leaves brushing",
        video_prompt="Drone pushes forward aggressively, threading the needle between two large foreground trees to reveal the house. The foreground branches blur and whip past the lens, creating intense speed and depth.",
    ),
    VideoStyle(
        style_id="VID_DRN_013", category="Drone Aerial", mood="Sunset Glamour",
        camera_motion="Low Angle Orbit", environmental_dynamics="Golden hour flare",
        video_prompt="Drone orbits the property at eye-level while pointing slightly up at the facade. Golden hour lighting hits the glass, creating moving, liquid-like reflections of the sunset sky.",
    ),
    VideoStyle(
        style_id="VID_DRN_014", category="Drone Aerial", mood="Winter/Cool",
        camera_motion="Slow Pull-Back", environmental_dynamics="Fog rolling",
        video_prompt="Drone slowly reverses away from a modern cabin or estate. Thick, volumetric fog or mist rolls realistically through the foreground trees, interacting with the 3D space.",
    ),
    VideoStyle(
        style_id="VID_DRN_015", category="Drone Aerial", mood="Modern",
        camera_motion="Tracking Subject", environmental_dynamics="Car pulling in",
        video_prompt="Drone smoothly tracks a luxury car pulling into the driveway. Match the vehicle's velocity perfectly, then pan up to frame the house as the car comes to a halt.",
    ),
    VideoStyle(
        style_id="VID_DRN_016", category="Drone Aerial", mood="Establishing",
        camera_motion="Crane Up & Tilt Down", environmental_dynamics="Horizon reveal",
        video_prompt="Drone starts at ground level looking straight ahead, rises vertically 50 feet, and slowly tilts the gimbal down to 45 degrees, revealing the geometric layout of the property.",
    ),
    VideoStyle(
        style_id="VID_DRN_017", category="Drone Aerial", mood="Night Luxury",
        camera_motion="Orbit", environmental_dynamics="Practicals glowing",
        video_prompt="Nighttime drone orbit. The sky is deep black. The house is illuminated purely by warm exterior landscape lighting and glowing windows. Lights do not flicker; perfect temporal stability.",
    ),
    VideoStyle(
        style_id="VID_DRN_018", category="Drone Aerial", mood="Action",
        camera_motion="Fast Skim", environmental_dynamics="Surface tension",
        video_prompt="Drone skims incredibly fast just inches above a flat surface (driveway or water) toward the house, decelerating smoothly right before impact. Intense foreground speed blur.",
    ),
    VideoStyle(
        style_id="VID_DRN_019", category="Drone Aerial", mood="Transition",
        camera_motion="Ascend to Cloud", environmental_dynamics="Atmospheric",
        video_prompt="Drone flies straight up from the backyard, accelerating into the sky until the camera is swallowed by a volumetric, realistic passing cloud. Perfect for scene transitions.",
    ),
    VideoStyle(
        style_id="VID_DRN_020", category="Drone Aerial", mood="Symmetrical",
        camera_motion="Dead-Center Push", environmental_dynamics="Perfect alignment",
        video_prompt="Perfectly centered, symmetrical drone push-in toward the main entrance. Zero lateral drift. The architecture scales up mathematically perfectly without AI warping.",
    ),

    # ── Dolly Interior / Exterior ─────────────────────────────────────────────
    VideoStyle(
        style_id="VID_DOL_021", category="Dolly Interior", mood="Architectural",
        camera_motion="Slow Push-In", environmental_dynamics="Volumetric light rays",
        video_prompt="Heavy, stabilized cinema dolly-in. Camera pushes physically through the hallway 3D space. Harsh, directional sunlight cuts through windows, creating visible, moving volumetric dust motes in the air.",
    ),
    VideoStyle(
        style_id="VID_DOL_022", category="Dolly Interior", mood="Intimate/Cozy",
        camera_motion="Micro-Slider Left", environmental_dynamics="Soft light falloff",
        video_prompt="Macro-level slider movement along a textured surface. Camera trucks left very slowly. Extremely shallow depth of field (f/1.4). Background living space is wrapped in creamy bokeh with soft light falloff.",
    ),
    VideoStyle(
        style_id="VID_DOL_023", category="Dolly Exterior", mood="Grand Entrance",
        camera_motion="Dolly Out & Tilt Up", environmental_dynamics="Shadows lengthening",
        video_prompt="Start tight on the luxury front door, execute a smooth dolly backward down the walkway while tilting up to reveal the full height of the house. Motion is perfectly linear.",
    ),
    VideoStyle(
        style_id="VID_DOL_024", category="Dolly Interior", mood="Spatial Depth",
        camera_motion="Push Through Doorway", environmental_dynamics="Threshold parallax",
        video_prompt="Cinematic push-through. Camera starts in a dimly lit room, dollying perfectly straight through a doorway threshold into a bright living room. Massive foreground parallax emphasizes 3D depth.",
    ),
    VideoStyle(
        style_id="VID_DOL_025", category="Dolly Interior", mood="High-End Retail",
        camera_motion="Lateral Track", environmental_dynamics="Specular glint rolling",
        video_prompt="Perfectly smooth horizontal truck-right movement parallel to a luxury kitchen. Lighting is highly controlled. Sharp specular highlights roll fluidly across glossy surfaces and metal hardware.",
    ),
    VideoStyle(
        style_id="VID_DOL_026", category="Dolly Interior", mood="Dynamic",
        camera_motion="Whip Pan to Push", environmental_dynamics="Action blur",
        video_prompt="Fast whip-pan from a blank wall ending locked onto a textured stone fireplace, immediately transitioning into a slow, tense dolly-in. Harsh side-light emphasizes 3D grooves.",
    ),
    VideoStyle(
        style_id="VID_DOL_027", category="Dolly Interior", mood="Scale Reveal",
        camera_motion="Pedestal Up", environmental_dynamics="Chandelier glint",
        video_prompt="Camera starts at waist height and executes a smooth, robotic vertical pedestal up to 8 feet high. The motion reveals the full depth of the room. Overhead glass chandeliers catch light dynamically.",
    ),
    VideoStyle(
        style_id="VID_DOL_028", category="Dolly Interior", mood="Symmetrical",
        camera_motion="Center Push", environmental_dynamics="Bilateral perfection",
        video_prompt="Wes Anderson-style dead-center symmetrical composition of a grand hallway. Perfectly straight, slow dolly-in. Left and right sides of the frame remain perfectly balanced.",
    ),
    VideoStyle(
        style_id="VID_DOL_029", category="Dolly Interior", mood="Hitchcock",
        camera_motion="Dolly Zoom (Zolly)", environmental_dynamics="Perspective warp",
        video_prompt="Subtle dolly-zoom. The camera slowly dollies backward while simultaneously zooming in optically. Foreground furniture remains the exact same size while the background walls compress dramatically.",
    ),
    VideoStyle(
        style_id="VID_DOL_030", category="Dolly Interior", mood="Living Space",
        camera_motion="Arc/Orbit", environmental_dynamics="Shadow shifting",
        video_prompt="Smooth, 90-degree arc shot tracking around a central coffee table or island. Deep parallax between the foreground object and the background walls. Shadows physically shift across the floor.",
    ),
    VideoStyle(
        style_id="VID_DOL_031", category="Dolly Interior", mood="Detail Focus",
        camera_motion="Reverse Track", environmental_dynamics="Expanding view",
        video_prompt="Slow backward tracking shot pulling away from a tight detail (like a vase). The room's architecture slowly encroaches on the edges of the frame, revealing the wide space.",
    ),
    VideoStyle(
        style_id="VID_DOL_032", category="Dolly Interior", mood="Organic",
        camera_motion="Handheld Drift", environmental_dynamics="Subtle sway",
        video_prompt="Cinematic handheld style. A very slow, organic, breathing camera movement. Gently drifting forward and swaying slightly to mimic human presence walking through the space.",
    ),
    VideoStyle(
        style_id="VID_DOL_033", category="Dolly Interior", mood="Luxury Floor",
        camera_motion="Low Dolly Push", environmental_dynamics="Reflections",
        video_prompt="Camera is positioned 1 foot off the ground. Smooth push forward over high-gloss marble or hardwood. The floor reflects the ceiling lights with perfect, dynamic geometric accuracy.",
    ),
    VideoStyle(
        style_id="VID_DOL_034", category="Dolly Exterior", mood="Reveal",
        camera_motion="Lateral Truck Left", environmental_dynamics="Foreground block",
        video_prompt="Camera trucks left. A massive foreground element (like a concrete pillar or tree trunk) wipes across the lens, revealing the stunning modern backyard and pool in sharp focus.",
    ),
    VideoStyle(
        style_id="VID_DOL_035", category="Dolly Interior", mood="High-Energy",
        camera_motion="Fast Push Over Counter", environmental_dynamics="Motion blur",
        video_prompt="High-kinetic energy. Camera pushes rapidly over the kitchen island toward the stove. Slight motion blur on the foreground objects. Sleek, modern, fast-paced.",
    ),
    VideoStyle(
        style_id="VID_DOL_036", category="Dolly Interior", mood="Moody",
        camera_motion="Slow Creep", environmental_dynamics="TV/Screen glow",
        video_prompt="Start static, then a very slow creep forward. Room is dimly lit. A television or media screen emits a soft, shifting, blue/white ambient glow illuminating the furniture.",
    ),
    VideoStyle(
        style_id="VID_DOL_037", category="Dolly Interior", mood="Flow",
        camera_motion="Steadicam Follow", environmental_dynamics="Dust motes",
        video_prompt="Smooth Steadicam tracking shot moving forward from foyer into main living space. Slow, deliberate pacing. Sunbeams filter through windows with visible, slowly drifting dust motes.",
    ),
    VideoStyle(
        style_id="VID_DOL_038", category="Dolly Interior", mood="Ceiling Focus",
        camera_motion="Tilt Up & Push", environmental_dynamics="Skylight parallax",
        video_prompt="Start focused on modern furniture, execute a smooth continuous tilt upwards while pushing forward to reveal vaulted ceilings and skylights. Perfect vertical alignment is maintained.",
    ),
    VideoStyle(
        style_id="VID_DOL_039", category="Dolly Interior", mood="Morning Vibe",
        camera_motion="Diagonal Slide", environmental_dynamics="Sunlight crawling",
        video_prompt="Slow lateral slider movement mixed with a forward push. As camera moves, morning sunlight creeps slowly across the hardwood floor. High-key, bright, crisp textures.",
    ),
    VideoStyle(
        style_id="VID_DOL_040", category="Dolly Interior", mood="Seamless Handover",
        camera_motion="Velocity Match", environmental_dynamics="Perfect 3D track",
        video_prompt="Match the exact composition of the anchor frame. Start completely static, then ease seamlessly into a fluid 3D push-in. No pixel stuttering; strict geometric retention.",
    ),

    # ── Sunset / Twilight ─────────────────────────────────────────────────────
    VideoStyle(
        style_id="VID_SUN_041", category="Sunset/Twilight", mood="Golden Hour",
        camera_motion="Slow Arc", environmental_dynamics="Lens flare shifting",
        video_prompt="Golden hour exterior wide. Sun is low on the horizon, blasting warm amber light across the facade. Slow arc shot. Photorealistic lens flare shifts and bends dynamically across the lens.",
    ),
    VideoStyle(
        style_id="VID_SUN_042", category="Sunset/Twilight", mood="Blue Hour",
        camera_motion="Static Pan", environmental_dynamics="Practicals glowing",
        video_prompt="Deep twilight blue hour. Ambient exterior light is cool and dim. Slow, stabilized pan across the property. Interior and landscape lights glow with warm orange-tungsten contrast.",
    ),
    VideoStyle(
        style_id="VID_SUN_043", category="Sunset/Twilight", mood="Reflection",
        camera_motion="Drone Hover", environmental_dynamics="Glass reflecting sky",
        video_prompt="Drone hovering at second-story height, looking at the modern glass facade. Windows act as perfect mirrors, reflecting an intensely vibrant pink and orange sunset sky. Clouds in reflection move.",
    ),
    VideoStyle(
        style_id="VID_SUN_044", category="Sunset/Twilight", mood="Dusk Transition",
        camera_motion="Pull Back", environmental_dynamics="Shadows swallowing space",
        video_prompt="Late dusk interior. Dolly out from a large window. Exterior light is rapidly fading. Inside, deep corners fall into rich shadow while remaining window light paints the floor coolly.",
    ),
    VideoStyle(
        style_id="VID_SUN_045", category="Sunset/Twilight", mood="Long Shadows",
        camera_motion="Push-In", environmental_dynamics="Shadows crawling",
        video_prompt="Late afternoon golden hour inside. Camera pushes in slowly. Sun is so low it casts dramatically long, stretched shadows of the window frames across the floor. Shadows maintain perfect perspective.",
    ),
    VideoStyle(
        style_id="VID_SUN_046", category="Sunset/Twilight", mood="Time-Lapse",
        camera_motion="Locked-off Static", environmental_dynamics="Light cycle",
        video_prompt="Time-lapse effect. Camera perfectly static. Natural sunlight rapidly sweeps across the floor, fades out, and interior practical lights bloom instantly as night falls.",
    ),
    VideoStyle(
        style_id="VID_SUN_047", category="Sunset/Twilight", mood="Morning Bloom",
        camera_motion="Static Pan", environmental_dynamics="Exposure ramp",
        video_prompt="Start in dark pre-dawn blue hour. Slow pan across the room as the sun breaches the horizon, rapidly warming the room with intense, golden hour volumetric light.",
    ),
    VideoStyle(
        style_id="VID_SUN_048", category="Sunset/Twilight", mood="Dusk Twinkle",
        camera_motion="Pull Back", environmental_dynamics="City lights turning on",
        video_prompt="Camera slowly pulls back from a window. Outside, the sky transitions from purple to black, and city lights or neighborhood streetlights sequentially turn on in the background.",
    ),
    VideoStyle(
        style_id="VID_SUN_049", category="Sunset/Twilight", mood="Exterior Dusk",
        camera_motion="Drone Hover", environmental_dynamics="Facade lights on",
        video_prompt="Drone hovers statically in front of house at blue hour. Exterior landscape and architectural uplighting fade on beautifully, illuminating the facade in warm tones.",
    ),
    VideoStyle(
        style_id="VID_SUN_050", category="Sunset/Twilight", mood="Silhouette",
        camera_motion="Lateral Track", environmental_dynamics="Sky gradient",
        video_prompt="Exterior tracking shot at the very end of sunset. House is completely unlit, forming a stark, graphic black silhouette against a blazing magenta and purple sky. Pure editorial mood.",
    ),
    VideoStyle(
        style_id="VID_SUN_051", category="Sunset/Twilight", mood="Water Reflection",
        camera_motion="Tilt Down", environmental_dynamics="Sky colors in pool",
        video_prompt="Golden hour over a backyard pool. Camera slowly tilts down from the vibrant orange sky to the pool water. The water perfectly reflects the sky, with gentle, fluid ripples.",
    ),
    VideoStyle(
        style_id="VID_SUN_052", category="Sunset/Twilight", mood="Through Trees",
        camera_motion="Tracking", environmental_dynamics="Strobe sun effect",
        video_prompt="Camera tracks sideways past a dense line of trees during sunset. The low sun bursts aggressively through the gaps in the trunks, creating a cinematic, flashing strobe effect on the lens.",
    ),
    VideoStyle(
        style_id="VID_SUN_053", category="Sunset/Twilight", mood="Cozy Evening",
        camera_motion="Slow Push to Fire", environmental_dynamics="Fireplace flickering",
        video_prompt="Cinematic dolly-in toward an outdoor firepit at dusk. Flames are dynamic, flickering naturally and casting shifting, warm ambient light onto the surrounding stone.",
    ),
    VideoStyle(
        style_id="VID_SUN_054", category="Sunset/Twilight", mood="Interior Glow",
        camera_motion="Push Through Glass", environmental_dynamics="Indoor/Outdoor transition",
        video_prompt="Twilight shot pushing from the dark exterior patio through an open sliding glass door into the warmly lit, glowing interior living room. Perfect exposure balance.",
    ),
    VideoStyle(
        style_id="VID_SUN_055", category="Sunset/Twilight", mood="Fade to Black",
        camera_motion="Slow Dolly Back", environmental_dynamics="Light extinguishing",
        video_prompt="Moody end-of-video shot. Camera dollies back slowly in a dimly lit room. The last remnants of sunset fade from the window, and the room falls into deep, cinematic blackness.",
    ),
    VideoStyle(
        style_id="VID_SUN_056", category="Sunset/Twilight", mood="High Contrast",
        camera_motion="Static", environmental_dynamics="Sun dipping behind roof",
        video_prompt="Locked off low-angle shot. The sun physically dips behind the sharp architectural roofline, instantly changing the exposure from bright high-key to a moody, silhouetted blue hour.",
    ),
    VideoStyle(
        style_id="VID_SUN_057", category="Sunset/Twilight", mood="Warmth",
        camera_motion="Macro Slider", environmental_dynamics="Sun across wood",
        video_prompt="Macro close-up on a hardwood floor or dining table. Slow slide right. A sharp beam of golden hour sunlight physically moves across the wood grain, revealing rich texture.",
    ),
    VideoStyle(
        style_id="VID_SUN_058", category="Sunset/Twilight", mood="City View",
        camera_motion="Push to Balcony", environmental_dynamics="Skyline parallax",
        video_prompt="Twilight push-in from the penthouse interior out toward the balcony. The city skyline in the background exhibits massive 3D parallax and twinkling lights against a purple sky.",
    ),
    VideoStyle(
        style_id="VID_SUN_059", category="Sunset/Twilight", mood="Atmospheric",
        camera_motion="Drone Pull-Up", environmental_dynamics="Mist at dusk",
        video_prompt="Drone pulls straight up above the property at dusk. A cool, atmospheric mist settles over the ground while the sky burns with remaining sunset colors.",
    ),
    VideoStyle(
        style_id="VID_SUN_060", category="Sunset/Twilight", mood="Match Cut Bridge",
        camera_motion="Day to Night", environmental_dynamics="Seamless transition",
        video_prompt="Anchor A is noon lighting, Anchor C is midnight. Generate a seamless, locked-off transition that bridges the two by rapidly accelerating the shifting shadows and lighting changes.",
    ),

    # ── Lighting Logic ────────────────────────────────────────────────────────
    VideoStyle(
        style_id="VID_LGT_061", category="Lighting Logic", mood="Dappled Sunlight",
        camera_motion="Handheld Drift", environmental_dynamics="Canopy shadow shift",
        video_prompt="Cinematic handheld drift in a sunroom. Light filters through a dense tree canopy outside, casting intricate, dappled sunlight patterns. As wind blows outside, dappled light dances dynamically.",
    ),
    VideoStyle(
        style_id="VID_LGT_062", category="Lighting Logic", mood="Overcast Softbox",
        camera_motion="Slow Pedestal", environmental_dynamics="Smooth roll-off",
        video_prompt="Overcast, diffused daylight exterior. No harsh shadows. Light wraps softly around the building geometry. Slow pedestal up. Materials look incredibly rich and color-accurate.",
    ),
    VideoStyle(
        style_id="VID_LGT_063", category="Lighting Logic", mood="Chiaroscuro/Noir",
        camera_motion="Slider Right", environmental_dynamics="High contrast reveal",
        video_prompt="Moody, high-contrast interior. Room is mostly dark, lit only by a single harsh shaft of light. Camera slides right, slowly revealing luxury furniture as it enters the stark beam.",
    ),
    VideoStyle(
        style_id="VID_LGT_064", category="Lighting Logic", mood="Practical Bloom",
        camera_motion="Push to Subject", environmental_dynamics="Atmospheric haze",
        video_prompt="Nighttime interior. Push-in toward a chandelier. The room has a very subtle cinematic atmospheric haze, causing the light source to bloom and glow softly into the space.",
    ),
    VideoStyle(
        style_id="VID_LGT_065", category="Lighting Logic", mood="Water Caustics",
        camera_motion="Tilt Down", environmental_dynamics="Reflected light dancing",
        video_prompt="Midday bright sun near a pool. Intense, dancing light caustics reflect off the moving water and paint rippling, dynamic light patterns onto the adjacent architectural walls.",
    ),
    VideoStyle(
        style_id="VID_LGT_066", category="Lighting Logic", mood="Neon/Modern",
        camera_motion="Slow Arc", environmental_dynamics="Color spill",
        video_prompt="Ultra-modern home at night with integrated LED strip lighting (blue/purple). Slow arc shot. Colored light spills accurately onto textures, creating deep, rich color gradients.",
    ),
    VideoStyle(
        style_id="VID_LGT_067", category="Lighting Logic", mood="Cloud Cover",
        camera_motion="Wide Static", environmental_dynamics="Light dimming/brightening",
        video_prompt="Locked-off wide shot of a living space. Ambient light in the room dims slightly and then brightens dynamically, simulating thick clouds passing over the sun outside.",
    ),
    VideoStyle(
        style_id="VID_LGT_068", category="Lighting Logic", mood="Fireplace Start",
        camera_motion="Static Close-up", environmental_dynamics="Ignition",
        video_prompt="Camera focused on a dark fireplace. Suddenly the gas ignites, instantly flooding the immediate surrounding area with warm, flickering, dynamic 3D light.",
    ),
    VideoStyle(
        style_id="VID_LGT_069", category="Lighting Logic", mood="Smart Home",
        camera_motion="Dolly In", environmental_dynamics="Lights sequentially on",
        video_prompt="Camera pushes down a dark hallway. As it moves, recessed overhead lights turn on sequentially just ahead of the camera, creating a runway effect.",
    ),
    VideoStyle(
        style_id="VID_LGT_070", category="Lighting Logic", mood="Skylight Shaft",
        camera_motion="Vertical Pan", environmental_dynamics="Dust motes",
        video_prompt="Start at the floor, slowly pan vertically up to a high skylight. A harsh, defined shaft of directional light cuts through the dim room, with dust motes swirling inside the beam.",
    ),
    VideoStyle(
        style_id="VID_LGT_071", category="Lighting Logic", mood="Under-Cabinet",
        camera_motion="Macro Orbit", environmental_dynamics="Gradients",
        video_prompt="Dark kitchen. Slow, deliberate arc shot around the edge of the island. Under-cabinet LED strips glow warmly, casting sharp, beautiful light gradients onto the backsplash.",
    ),
    VideoStyle(
        style_id="VID_LGT_072", category="Lighting Logic", mood="Mirror Bounce",
        camera_motion="Slide Left", environmental_dynamics="Reflected sunlight",
        video_prompt="Camera slides left across a bathroom vanity. A beam of sunlight hits the mirror and physically bounces onto the opposite wall, moving across the tile realistically with the camera motion.",
    ),
    VideoStyle(
        style_id="VID_LGT_073", category="Lighting Logic", mood="Lightning/Storm",
        camera_motion="Static Wide", environmental_dynamics="Strobe flash",
        video_prompt="Moody night interior. Outside the window, a realistic, bright flash of lightning illuminates the entire backyard and casts sudden, sharp, instantaneous shadows across the interior room.",
    ),
    VideoStyle(
        style_id="VID_LGT_074", category="Lighting Logic", mood="Glint & Glare",
        camera_motion="Fast Tracking", environmental_dynamics="Specular rolls",
        video_prompt="Fast tracking shot past a row of stainless steel appliances or glass windows. Extremely sharp, intense specular highlights roll rapidly across the surfaces, blinding the lens briefly.",
    ),
    VideoStyle(
        style_id="VID_LGT_075", category="Lighting Logic", mood="High-Key Wash",
        camera_motion="Push-In", environmental_dynamics="Overexposure ramp",
        video_prompt="Bright, airy morning room. Push-in toward the large windows. The exposure is intentionally pushed high, washing the room in soft, angelic white light with minimal shadow.",
    ),
    VideoStyle(
        style_id="VID_LGT_076", category="Lighting Logic", mood="Warm Amber",
        camera_motion="Handheld", environmental_dynamics="Sconce glow",
        video_prompt="Intimate handheld shot in a hallway. The only light source is a vintage brass wall sconce. The light emits a deep, warm amber hue that falls off rapidly into deep crushed black shadows.",
    ),
    VideoStyle(
        style_id="VID_LGT_077", category="Lighting Logic", mood="Curtain Filter",
        camera_motion="Dolly Forward", environmental_dynamics="Light softening",
        video_prompt="Camera pushes toward a window. Suddenly, a sheer white curtain blows across the window frame, instantly changing the harsh direct sunlight into a soft, beautiful diffused glow in the room.",
    ),
    VideoStyle(
        style_id="VID_LGT_078", category="Lighting Logic", mood="Basement Noir",
        camera_motion="Push Down Stairs", environmental_dynamics="Shadow expansion",
        video_prompt="Camera slowly dollies down a dark staircase. A single bare bulb swings slightly from the ceiling, causing the shadows of the banister to warp and swing dynamically across the walls.",
    ),
    VideoStyle(
        style_id="VID_LGT_079", category="Lighting Logic", mood="Exterior Spotlight",
        camera_motion="Drone Orbit", environmental_dynamics="Wall grazing",
        video_prompt="Night drone orbit. Harsh exterior ground spotlights graze up the textured stone facade. The lighting highlights every bump and ridge in the stone with micro-shadows.",
    ),
    VideoStyle(
        style_id="VID_LGT_080", category="Lighting Logic", mood="Seamless Bridge",
        camera_motion="Day to Dusk", environmental_dynamics="Temporal shift",
        video_prompt="Bridge Anchor A (Day) to Anchor C (Dusk) with a seamless, fluid 3D dolly-in. The physics engine must calculate the rapid darkening of the room while maintaining spatial geometry.",
    ),

    # ── Macro / Detail ────────────────────────────────────────────────────────
    VideoStyle(
        style_id="VID_MAC_081", category="Macro/Detail", mood="Wood/Stone",
        camera_motion="Slider Left", environmental_dynamics="Grain depth",
        video_prompt="Extreme close-up on natural wood grain. Slow, consistent slider movement left. Harsh side-lighting rakes across the surface, highlighting the deep 3D relief of the texture.",
    ),
    VideoStyle(
        style_id="VID_MAC_082", category="Macro/Detail", mood="Glass/Metal",
        camera_motion="Arc Orbit", environmental_dynamics="Refraction shift",
        video_prompt="Close-up on a glass partition or hardware. Smooth orbital camera movement. The background refracts and bends through the glass dynamically. Specular highlights slide smoothly.",
    ),
    VideoStyle(
        style_id="VID_MAC_083", category="Macro/Detail", mood="Water/Liquid",
        camera_motion="Slow Push", environmental_dynamics="Surface tension",
        video_prompt="Close-up on a pool edge or fountain. Very slow push-in. Water surface ripples gently, catching sunlight and reflecting the environment perfectly.",
    ),
    VideoStyle(
        style_id="VID_MAC_084", category="Macro/Detail", mood="Fabric/Upholstery",
        camera_motion="Rack Focus", environmental_dynamics="Soft lighting",
        video_prompt="Close-up on high-end furniture fabric. Start completely out of focus (creamy bokeh), smoothly rack focus to reveal the sharp, intricate weave of the upholstery.",
    ),
    VideoStyle(
        style_id="VID_MAC_085", category="Macro/Detail", mood="Foliage/Plants",
        camera_motion="Handheld Macro", environmental_dynamics="Leaves trembling",
        video_prompt="Macro shot of an indoor plant leaf against a window. Cinematic handheld breathing. The leaf trembles very slightly as if touched by an AC breeze.",
    ),
    VideoStyle(
        style_id="VID_MAC_086", category="Macro/Detail", mood="Leather/Patina",
        camera_motion="Tilt Down", environmental_dynamics="Light roll-off",
        video_prompt="Close-up on a leather chair. Smooth tilt down. The specular light rolls off the curves and creases of the leather, highlighting its premium quality.",
    ),
    VideoStyle(
        style_id="VID_MAC_087", category="Macro/Detail", mood="Architectural Seam",
        camera_motion="Push In", environmental_dynamics="Perfect geometry",
        video_prompt="Extreme close-up of where hardwood floor meets marble tile. Slow push-in. Emphasizes perfect craftsmanship and straight, rigid lines. No AI morphing of the seam.",
    ),
    VideoStyle(
        style_id="VID_MAC_088", category="Macro/Detail", mood="Brick/Masonry",
        camera_motion="Lateral Slide", environmental_dynamics="Shadow play",
        video_prompt="Close-up on an exposed brick wall. Horizontal slider move. The deep shadows in the mortar joints shift dynamically with the 3D parallax.",
    ),
    VideoStyle(
        style_id="VID_MAC_089", category="Macro/Detail", mood="Light Fixture",
        camera_motion="Subtle Orbit", environmental_dynamics="Bulb filament",
        video_prompt="Macro shot of a bare filament bulb or luxury pendant. Very slow orbit. The glowing filament remains sharp while the background spins in soft bokeh.",
    ),
    VideoStyle(
        style_id="VID_MAC_090", category="Macro/Detail", mood="Faucet/Water",
        camera_motion="Static Close-up", environmental_dynamics="Drop falling",
        video_prompt="Macro locked-off shot of a matte black bathroom faucet. A single, photorealistic drop of water forms, catches the light, and falls seamlessly into the sink.",
    ),

    # ── High-Energy ───────────────────────────────────────────────────────────
    VideoStyle(
        style_id="VID_HYP_091", category="High-Energy", mood="Speed Ramp",
        camera_motion="Fast Push -> Slow", environmental_dynamics="Kinetic energy",
        video_prompt="Start with aggressively fast push toward the kitchen island, suddenly speed-ramp into extreme, buttery slow-motion right before impact. Intense cinematic weight.",
    ),
    VideoStyle(
        style_id="VID_HYP_092", category="High-Energy", mood="Whip Pan Left",
        camera_motion="Blur to Sharp", environmental_dynamics="Transition",
        video_prompt="High-speed whip pan to the left. The scene blurs entirely into horizontal streaks, then snaps perfectly into sharp focus on the new architectural subject.",
    ),
    VideoStyle(
        style_id="VID_HYP_093", category="High-Energy", mood="Push Through",
        camera_motion="Object passage", environmental_dynamics="Depth illusion",
        video_prompt="Camera pushes rapidly forward, passing physically through the gap between two foreground objects to reveal the wide room behind.",
    ),
    VideoStyle(
        style_id="VID_HYP_094", category="High-Energy", mood="Crash Zoom",
        camera_motion="Snap Focus", environmental_dynamics="Detail highlight",
        video_prompt="Camera executes a rapid, jarring crash zoom (instant optical magnification) from a wide shot directly into a tight detail of a high-end fixture.",
    ),
    VideoStyle(
        style_id="VID_HYP_095", category="High-Energy", mood="360 Roll",
        camera_motion="Barrel Roll", environmental_dynamics="Disorienting/Cool",
        video_prompt="Interior hallway. Camera moves forward while executing a slow, deliberate 360-degree barrel roll (rotation on the Z-axis). Perfect geometric retention.",
    ),
    VideoStyle(
        style_id="VID_HYP_096", category="High-Energy", mood="The Zolly Snap",
        camera_motion="Rapid Dolly Zoom", environmental_dynamics="Warp speed",
        video_prompt="Extreme, fast-paced Dolly Zoom. Foreground object remains locked in frame while the background violently compresses behind it in a fraction of a second.",
    ),

    # ── Seamless Bridge ───────────────────────────────────────────────────────
    VideoStyle(
        style_id="VID_SML_097", category="Seamless Bridge", mood="Start->End Anchor",
        camera_motion="Ramped Pan", environmental_dynamics="Temporal stability",
        video_prompt="Start static on Anchor A. Ease into a horizontal pan right. Decelerate perfectly to match the exact composition, lighting, and geometry of Anchor C.",
    ),
    VideoStyle(
        style_id="VID_SML_098", category="Seamless Bridge", mood="Start->End Anchor",
        camera_motion="Arc Connection", environmental_dynamics="No geometry warp",
        video_prompt="Bridge Frame A and Frame C with a cinematic 3D arc shot. Maintain structural rigidity of the corners. No AI hallucination or morphing occurs during the bridge.",
    ),
    VideoStyle(
        style_id="VID_SML_099", category="Seamless Bridge", mood="Start->End Anchor",
        camera_motion="Vertical Pedestal", environmental_dynamics="Lighting consistency",
        video_prompt="Connect low-angle Anchor A to high-angle Anchor C via a smooth vertical lift. Ceiling architecture and lighting fixtures remain consistent throughout motion.",
    ),
    VideoStyle(
        style_id="VID_SML_100", category="Seamless Bridge", mood="Start->End Anchor",
        camera_motion="The Grand Reveal", environmental_dynamics="Zero jitter",
        video_prompt="Absolute perfection. Start with zero jitter on Frame A. Execute a sweeping push-through of the threshold, landing perfectly aligned with the wide-shot geometry of Frame C.",
    ),
]

# Fast lookup by ID
STYLE_BY_ID: dict[str, VideoStyle] = {s.style_id: s for s in STYLES}

# Ordered unique categories preserving first-seen order
CATEGORY_ORDER: list[str] = list(dict.fromkeys(s.category for s in STYLES))
