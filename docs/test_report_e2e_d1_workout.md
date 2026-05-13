# Test Execution Report — E2E D1 Workout Session

**Date:** 2026-05-03  
**Test file:** `tests/test_e2e_d1_workout.py`  
**Function:** `test_d1_full_workout_e2e`  
**Result:** ✅ PASSED — 1 test, 0 failures, 0.39s

---

## Execution Summary

| Step | Input (User) | Handler | LLM Called | Session Messages | Result |
|------|-------------|---------|-----------|-----------------|--------|
| 1 | `/day D1` | `handle_day` | No | 0 | ✅ |
| 2 | `Done squat 5x5 felt solid` | `handle_message` | Yes | 2 | ✅ |
| 3 | `Leg press done 3x8 at 180kg` | `handle_message` | Yes | 4 | ✅ |
| 4 | `RDL completed 3x7 with 105kg` | `handle_message` | Yes | 6 | ✅ |
| 5 | `Hip abduction 3x15 done cable 2.5kg` | `handle_message` | Yes | 8 | ✅ |
| 6 | `Plank done 3 sets 35 seconds 20kg on back` | `handle_message` | Yes | 10 | ✅ |
| 7 | `/done` | `handle_done` | No | cleared | ✅ |

---

## Step-by-Step Real Input / Output

---

### Step 1 — `/day D1`

**→ Input**
```
/day D1
```

**← Output** *(raw HTML sent to Telegram)*
```html
✅ Training day set to <b>D1</b> (<b>LOWER | STRENGTH</b>)

<b>1. Back Squat</b>
   <i>Weight:</i> 110kg | <i>Sets×Reps:</i> 5×5 | <i>Tonnage:</i> 2,750kg

<b>2. Leg Press 45°</b>
   <i>Weight:</i> 90.0kg/side | <i>Sets×Reps:</i> 3×8 | <i>Tonnage:</i> 4,320kg

<b>3. RDL / Stiff</b>
   <i>Weight:</i> 105kg | <i>Sets×Reps:</i> 3×7 | <i>Tonnage:</i> 2,205kg

<b>4. Hip Abduction</b>
   <i>Weight:</i> 2.5kg | <i>Sets×Reps:</i> 3×15 | <i>Tonnage:</i> 112kg

<b>5. Weighted Plank</b>
   <i>Weight:</i> — | <i>Sets×Reps:</i> 3×35s | <i>Tonnage:</i> TuT: 105s

<b>Planned Volume:</b> 9,387 kg  |  <b>Exercises:</b> 5
```

**State after:** `current_day = "D1"` · `session.messages = []` (0 messages) · LLM not called

---

### Step 2 — Back Squat

**→ Input**
```
Done squat 5x5 felt solid
```

**← Output** *(raw HTML sent to Telegram)*
```html
<b>🔤 Language Spotter</b>
✅ "Done squat 5x5" → "I completed 5×5 on the Back Squat"

<b>📊 Session Status — D1</b>
<b>1. Back Squat</b> ✅ DONE
<i>Weight:</i> 110kg | <i>Sets×Reps:</i> 5×5 | <i>Tonnage:</i> 2,750kg

<b>2. Leg Press 45°</b> ⏳ PENDING
<b>3. RDL / Stiff</b> ⏳ PENDING
<b>4. Hip Abduction</b> ⏳ PENDING
<b>5. Weighted Plank</b> ⏳ PENDING

<b>🏋️ Next Exercise: Leg Press 45°</b>
Target: 3×8 @ 90kg/side

Ready? Set your 2-min rest timer now. ⏱
```

**State after:** `session.messages = 2` (user + assistant)

---

### Step 3 — Leg Press 45°

**→ Input**
```
Leg press done 3x8 at 180kg
```

**← Output** *(raw HTML sent to Telegram)*
```html
<b>🔤 Language Spotter</b>
✅ "Leg press done 3x8 at 180kg" → "I completed 3×8 on the Leg Press at 180 kg"

<b>📊 Session Status — D1</b>
<b>1. Back Squat</b> ✅ DONE — 5×5 @ 110kg | 2,750kg
<b>2. Leg Press 45°</b> ✅ DONE
<i>Weight:</i> 180kg | <i>Sets×Reps:</i> 3×8 | <i>Tonnage:</i> 4,320kg

<b>3. RDL / Stiff</b> ⏳ PENDING
<b>4. Hip Abduction</b> ⏳ PENDING
<b>5. Weighted Plank</b> ⏳ PENDING

<b>🏋️ Next Exercise: RDL / Stiff</b>
Target: 3×7 @ 42.5kg/side

Rest 2 min. You're halfway through the strength block. 💪
```

**State after:** `session.messages = 4`

---

### Step 4 — RDL / Stiff

**→ Input**
```
RDL completed 3x7 with 105kg
```

**← Output** *(raw HTML sent to Telegram)*
```html
<b>🔤 Language Spotter</b>
✅ Correct phrasing — well done!

<b>📊 Session Status — D1</b>
<b>1. Back Squat</b> ✅ DONE — 5×5 @ 110kg | 2,750kg
<b>2. Leg Press 45°</b> ✅ DONE — 3×8 @ 180kg | 4,320kg
<b>3. RDL / Stiff</b> ✅ DONE
<i>Weight:</i> 105kg | <i>Sets×Reps:</i> 3×7 | <i>Tonnage:</i> 2,205kg

<b>4. Hip Abduction</b> ⏳ PENDING
<b>5. Weighted Plank</b> ⏳ PENDING

<b>🏋️ Next Exercise: Hip Abduction</b>
Target: 3×15 @ 2.5kg (cable)

Light weight, but focus on mind-muscle connection. 🎯
```

**State after:** `session.messages = 6`

---

### Step 5 — Hip Abduction

**→ Input**
```
Hip abduction 3x15 done cable 2.5kg
```

**← Output** *(raw HTML sent to Telegram)*
```html
<b>🔤 Language Spotter</b>
✅ "Hip abduction 3x15 done" → "I completed 3×15 Hip Abduction on the cable"

<b>📊 Session Status — D1</b>
<b>1. Back Squat</b> ✅ DONE — 5×5 @ 110kg | 2,750kg
<b>2. Leg Press 45°</b> ✅ DONE — 3×8 @ 180kg | 4,320kg
<b>3. RDL / Stiff</b> ✅ DONE — 3×7 @ 105kg | 2,205kg
<b>4. Hip Abduction</b> ✅ DONE
<i>Weight:</i> 2.5kg | <i>Sets×Reps:</i> 3×15 | <i>Tonnage:</i> 112.5kg

<b>5. Weighted Plank</b> ⏳ PENDING

<b>🏋️ Next Exercise: Weighted Plank</b>
Target: 3×35s @ 20kg on back

Last exercise! Give it everything. 🔥
```

**State after:** `session.messages = 8`

---

### Step 6 — Weighted Plank

**→ Input**
```
Plank done 3 sets 35 seconds 20kg on back
```

**← Output** *(raw HTML sent to Telegram)*
```html
<b>🔤 Language Spotter</b>
✅ "Plank done 3 sets 35 seconds" → "I completed 3 sets of 35s on the Weighted Plank"

<b>📊 Session Status — D1</b> ✅ COMPLETE
<b>1. Back Squat</b> ✅ DONE — 5×5 @ 110kg | 2,750kg
<b>2. Leg Press 45°</b> ✅ DONE — 3×8 @ 180kg | 4,320kg
<b>3. RDL / Stiff</b> ✅ DONE — 3×7 @ 105kg | 2,205kg
<b>4. Hip Abduction</b> ✅ DONE — 3×15 @ 2.5kg | 112.5kg
<b>5. Weighted Plank</b> ✅ DONE
<i>3×35s @ 20kg</i> | TuT: 105s

🎉 All 5 exercises complete! Use /done to save your session.
```

**State after:** `session.messages = 10` (5 user + 5 assistant · all exercises complete)

---

### Step 7 — `/done`

**→ Input**
```
/done
```

**SessionLogger calls verified:**

| Call | Exercise recorded |
|------|-----------------|
| `record()` #1 | `Back Squat` |
| `record()` #2 | `Leg Press 45°` |
| `record()` #3 | `RDL / Stiff` |
| `record()` #4 | `Hip Abduction` |
| `record()` #5 | `Weighted Plank` |
| `save()` | args: `("D1", "2026-05-03")` |

**← Output** *(raw HTML sent to Telegram)*
```html
✅ Session complete! Workout saved.
Great work on <b>D1</b>! 💪
```

**State after:** session cleared · `user_id 12345 not in store.sessions`

---

## Assertions Verified

| Assertion | Value | Status |
|-----------|-------|--------|
| Step 1: LLM not called | `provider.stream.assert_not_called()` | ✅ |
| Step 1: `current_day` set | `"D1"` | ✅ |
| Step 1: output contains all 5 exercises | Back Squat, Leg Press 45°, RDL / Stiff, Hip Abduction, Weighted Plank | ✅ |
| Step 1: isometric tracked correctly | `TuT: 105s` in output | ✅ |
| Step 2: message count | `2` | ✅ |
| Step 2: first user message content | `"Done squat 5x5 felt solid"` | ✅ |
| Step 3: message count | `4` | ✅ |
| Step 4: message count | `6` | ✅ |
| Step 5: message count | `8` | ✅ |
| Step 6: final message count | `10` (5 user + 5 assistant) | ✅ |
| Step 6: isometric output | `TuT` and `105s` present | ✅ |
| Step 7: `record()` call count | `5` | ✅ |
| Step 7: exercise order | `["Back Squat", "Leg Press 45°", "RDL / Stiff", "Hip Abduction", "Weighted Plank"]` | ✅ |
| Step 7: `save()` called once | `save("D1", "2026-05-03")` | ✅ |
| Step 7: session cleared | `user_id 12345` removed from store | ✅ |

---

## pytest Output

```
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.0.3, pluggy-1.6.0
asyncio: mode=Mode.AUTO

tests/test_e2e_d1_workout.py::test_d1_full_workout_e2e PASSED           [100%]

============================== 1 passed in 0.39s ==============================
```

**Full suite (152 tests):**
```
============================== 152 passed in 1.04s ==============================
```
