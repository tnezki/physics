# Physics Pacing and Resource Readiness Audit

**Audit date:** 30 October 2026  
**Purpose:** Preserve a verified cross-chapter readiness check and the exact Chapter 5 production queue, without altering approved curriculum pacing.  
**Authority:** [Physics Master Curriculum Catalog](PHYSICS_MASTER_CURRICULUM_CATALOG.md) and [structured catalog](physics_master_curriculum_catalog.json). This document supplements them. It is not a new day-by-date school calendar.

## A. What is verified, and what is not

**Verified structurally:** The installed public `physics/curriculum/` catalog has nine chapters in approved order **1, 2, 3, 4, 5, 6, 10, 12, 9**; 25 distinct natural sections; **82** teacher lesson periods; **25** independent section reading/consolidation periods; **107** total core instructional periods. IDs are unique, and the section arithmetic is consistent. Chapter 5's eight Think Sheet PDFs, four lab documents, and four teacher-guide document filenames agree with the purchased Drive folder listings. The existing original Chapter 5.1.1 interactive is in the public Physics repository, and the protected `lesson_5_1_1` folder contains `student.html`, `student.pdf`, separate teacher materials, print sections, assets, and offline interactive files in Drive.

**Not verified:** A date-anchored 2026–27 school calendar, availability of every classroom resource, classroom-ready performance of every third-party interactive on students' iPads, access controls for every private shared file, detailed Question Bank item-to-target matching, or finalized original section readings. Do not interpret a resource audit as proof a complete lesson packet exists.

**Resource counts:** 41 explicitly mapped digital-use occurrences, 31 distinct URL strings, not 31 successfully tested student browser applications. Some URL strings are chapter landing pages rather than direct activities. Verify direct launch and PDF links lesson-by-lesson. Automated public fetches can return permission/robot blocks, which are not proof of classroom failure.

**One metadata caveat:** The Chapter 1 `UsingGraphsShortVersion.docx` item is a purchased BONUS file, outside the standard Think Sheet/lab inventory; its absence from those inventory arrays is intentional, not a missing paid resource.

## B. Time and course sequence

| Publisher chapter (teaching order) | Publisher-based lessons | Section readings | Core periods | Main pre-build check |
|---|---:|---:|---:|---|
| 1 — Graphs and Relationships | 7 | 2 | **9** | First-day Dune Buggy time; Desmos/Stopping Distance links |
| 2 — 1-D Kinematics | 11 | 3 | **14** | Pace Tracer cameras/markers; combined publisher Days 9–10 |
| 3 — Newton's Laws | 10 | 3 | **13** | Publisher Days 5–6 and 8–9 merges; physical lab setup |
| 4 — Free Fall/Projectiles | 8 | 3 | **11** | 40–50-minute video lab; combined Days 7–8; launcher data backup |
| 5 — Momentum/Collisions | 10 | 3 | **13** | Cart/balloon equipment; correct timing for Cart and Brick |
| 6 — Work/Energy | 9 | 3 | **12** | 35–45-minute Uphill lab; Vernier sensors; friction/energy modeling |
| 10 — Waves/Sound | 8 | 3 | **11** | Pendulum Paint setup; microphones; standing-wave prerequisite |
| 12 — Mirrors | 9 | 2 | **11** | Mirrors, low-risk light sources and stands; spacious ray diagrams |
| 9 — Circuits (last) | 10 | 3 | **13** | 35–45-minute charge-flow lab, circuit parts, short-circuit/broken-glass safeguards |
| **TOTAL** | **82** | **25** | **107** | Pacing unchanged |

**Separate meeting allocation:** If the approved practice of **one Monday pretest review and one separate paper test per chapter** is implemented for all nine chapters, there are **18 additional chapter review/test meetings**, giving **at least 125 course meetings (107 + 9 + 9)** before other Modeling Mondays, assessment follow-ups, extension days, holidays, absences, snow days, and buffers. This 125 is a planning calculation, **not a claim that 125 dates are available**. A 42-minute Modeling Monday is not automatically suitable for a 40–50-minute full lab. The complete date-to-date calendar is **unverified**. Senior cutoff: 7 May 2027; continuing students: 9 June 2027, as previously documented, not rechecked against a current school calendar. Do not silently cut the 107-day plan to fit.

**No homework:** Each student's required practice, reading, data analysis and writing happen during class. When a later activity uses prior lab measurements (for example, Chapter 4 Launcher Speed → Hit the Target), provide teacher-verified fallback data for absent students so their work is self-contained.

## C. Four compressed publisher-day lessons that require timing validation

| Lesson | Publisher days merged | Safeguard |
|---|---|---|
| 2.3.2 — Velocity-Time Graphs / Pace Tracer 2 | 9–10 | Test camera/marker and assignment completion in 54 minutes; omit publisher quiz/redundant practice |
| 3.2.2 — Free-Body Diagrams | 5–6 | Keep force representation and interactive; limit repeated Concept Builders |
| 3.3.2 — Force, Mass, Acceleration | 8–9 | Keep Force Interactive and conceptual predictions; trim long calculation sets |
| 4.2.2 — Projectile Tables/Diagrams | 7–8 | Retain horizontal/vertical models, use selected worksheet examples, remove repeated tasks |

These are **provisional implementation choices**. They do not trigger an immediate increase to the core plan. Report measured timing or student difficulty after classroom use.

## D. Readiness gates before any student lesson is marked complete

1. **Publisher fidelity:** Verify the relevant Conceptual Physics day plan, tutorial reading, purchased Think Sheet and lab/teacher guide. Preserve its effective lesson sequence. **Do not impose one fixed Notes/Lab/Think-Sheet order.** The existing 5.1.1 pilot sequence is notes/discussion → purchased Think Sheet pair practice → Marshmallow Launcher physical lab → optional synthesis.
2. **Learning outcome:** Identify the one or two main conceptual claims, terms fully defined and highlightable, essential representation(s), limited calculations, and evidence students should create in class. No assigned homework.
3. **Lesson timing:** Build for a normal 54-minute period; adapt only with an explicit 42-minute Modeling Monday plan. Keep full-length experiment and substantial practice from competing for the same minutes.
4. **Equipment and safety:** List exact supplies, setup, troubleshooting, and safe controls. Never copy unsafe suggestions such as intentionally heating shorted battery wires or students handling broken bulb glass. For launches/collisions, provide measurement/setup and data fallbacks.
5. **Student digital check:** On an actual student iPad, follow agenda → Google Drive PDF → Send a Copy → Notability; test clickable PDF-to-interactive links, tab/camera/mic permissions, and screenshot/annotation workflows as relevant. A successful prior 5.1.1 PDF test does not prove all other third-party interactives work.
6. **Student packet:** Coherent protected student PDF + HTML, readable reflow, genuine interactivity labeled as such, correctly aligned multiple-choice options, large drawing/response spaces, independently printable sections on separate PDF pages, no invisible hyperlinks.
7. **Teacher companion:** Same order and questions as student packet with inline facilitation, keyed explanations, material lists, prep and safety, common misconceptions, model answers, times and printer notes; teacher files remain private.
8. **Publish/distribute safely:** Public `physics/lessons/ch_XX/lesson_X_Y_Z/interactives/` only contains original independently publishable interactives/assets; private/student/teacher PDFs and purchased-derived materials stay in the synced `~Curriculum/__Physics/lessons_google_drive/ch_XX/chXX_lessons/lesson_X_Y_Z/` location. Confirm actual private file sharing before sending agenda links. No Git operations by assistant; teacher reviews/pushes via GitHub Desktop.
9. **Assessment tracking:** Use purchased Question Bank only privately to match items to learning goals when creating review, Quick Checks and chapter tests; paper-duplex scan + teacher-reviewed AI/Portfolio workflows. Question Bank item-level audit is **pending** and must not be claimed complete.

## E. Chapter 5 — immediate build queue (13 core periods)

**Use existing pilot as design reference, not as a target for unsolicited repairs.** The protected pilot exists in Drive at `ch_05/ch05_lessons/lesson_5_1_1/`; the public original interactive exists at `physics/lessons/ch_05/lesson_5_1_1/interactives/motion_and_launcher_lab.html`. The student PDF filename is `student.pdf`; previously used Drive file ID `1d0peY6_lz6mmnB6BDwbg4ATHWRYgEP5-` was observed again in the protected folder. The user has reported successful transfer to Notability with its external interactive link.

| Position | Lesson ID | Main experience | Required/selected source | Preparation or watchpoint |
|---:|---|---|---|---|
| 1 | 5.1.1 | Momentum, impulse, Marshmallow Launcher | `Lab1_MarshmallowLauncher.docx`; `Mom1_ImpulseMomentum.pdf` | **Pilot exists; preserve as is**; hygiene, 15–20-minute lab |
| 2 | **5.1.2** | Balloon Toss: force versus stopping time | `Lab2_BalloonToss.docx`; `Mom2_ImpulseMomentumChange.pdf` | **Next to build**; teacher demonstration 25–40 min; safe splash/cleanup, selected calculations |
| 3 | 5.1.3 | Impulse and safety examples | `Mom3_ImpDeltaPApplicns.pdf` | Seatbelts, airbags, catching/landing, guided explanations not equation drills |
| 4 | 5.1.R | **Section reading/consolidation** | Physics Classroom Momentum Lesson 1; Hewitt Ch6; OpenStax §8.1 | Full period, original reading plus selected applications and reflection |
| 5 | 5.2.1 | Explosion Analysis: unequal-mass spring carts | `Lab3_ExplosionAnalysis.docx`; `Mom4_ActionReaction.pdf` | Vernier tracks/carts; 30–40 min; calibrated video-data alternative |
| 6 | 5.2.2 | Exploding Carts simulation + Red/Blue cart comparison | `Mom5_RedCartVsBlueCart.pdf`; Exploding Carts interactive | Verify direct interactive launch on iPad; demo cart mass ratios |
| 7 | 5.2.3 | System momentum before/after explosion | `Mom6_ExplosionAnalysis.pdf` | System boundary, sign direction, quantitative table |
| 8 | 5.2.R | **Section reading/consolidation** | Physics Classroom Momentum Lesson 2; Hewitt Ch6; OpenStax §8.2 | Full period, system momentum and evidence-backed conservation |
| 9 | 5.3.1 | Collision Carts — hit and stick | `Mom7_CollisionAnalysis.pdf`; Collision Carts | Use **inelastic mode**; avoid requiring KE calculations |
| 10 | 5.3.2 | Collision Carts — hit and bounce | Selected `Mom7_CollisionAnalysis.pdf`; Collision Carts | Use **elastic mode**; direction and signs matter |
| 11 | 5.3.3 | Cart and Brick real collision | `Lab4_CartAndTheBrick.docx` | Correct physical time calibration; original guide's 10-ticks-per-second simplification is not accurate; plan 35–45 min combined |
| 12 | 5.3.4 | Fish Catch, proportional reasoning | `Mom8_ProportionalReasoning.pdf`; Fish Catch | Shared velocity and inverse mass relationship; verify exact link and iPad use |
| 13 | 5.3.R | **Section reading/consolidation** | Physics Classroom Momentum Lesson 2; Hewitt Ch6; OpenStax §8.3 intro | Full period; synthesis before chapter review/test |

**Separate:** Monday Chapter 5 review (not within 13) and separate printed chapter test (not within 13). Use approved review-page pattern and private Question Bank, with independent grade/evidence checks as planned.

**Purchased Chapter 5 access pointers:** Think PDFs: <https://drive.google.com/drive/folders/1wO1WJZZ30GNiuJA2_MlHQbWc33EFlsDy>; student labs: <https://drive.google.com/drive/folders/14BwUoaY29NQa_Ri_hjCa0CLV_Qfo2MXI>; teacher guides: <https://drive.google.com/drive/folders/1145e30TABOLFZlhZb-mY2Ia6rEpwXFxC>. The eight Think Sheet, four lab and four guide filenames were checked against those folders on 30 October 2026. Bought files are not copied into the public catalog.

**Optional / not core:** Greatest value from PhET Collision Lab, SMU observational demos, hit-and-stick alternate physical lab and publisher video tutorials is as targeted support, not an automatic extra assignment. Avoid introducing kinetic-energy conservation until Chapter 6.

**Chapter 5 production sequence:** Preserve 5.1.1 → build 5.1.2 → 5.1.3 → 5.1.R → 5.2.1 → 5.2.2 → 5.2.3 → 5.2.R → 5.3.1 → 5.3.2 → 5.3.3 → 5.3.4 → 5.3.R. All future repository/private Drive lesson files should be routed through **one local-only Curriculum Transfer v3 ZIP per build batch**, with separate approved roots; do not send a standalone component file.

## F. Follow-up work that does not block constructing Chapter 5 lessons

- Full **day/date calendar** using actual 2026–27 school dates and class meeting pattern; no fabricated dates.
- Teacher check of physical cart/mass/balloon setup, quantitative measurement procedure and consumable supply levels.
- Item-level Question Bank matching, needed before building the formal chapter assessment, not before classroom concepts/labs.
- Confirm all direct interactive URLs in browser and all PDF links on student devices *as each relevant lesson is built*. Public site access checks are not equivalent to local iPad validation.
- Author all 25 original section readings, their questions and appropriate supplement-source references; this is future lesson production, not part of the resource catalog audit.

**Change-control rule:** No current pacing changes. If classroom evidence forces a change, document the observation, proposed adjustment and its effect on 107 days *before* changing the approved catalog.
