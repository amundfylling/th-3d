# IKV v3 on the parametric skater (superseded geometry)

These are the saved outputs of `moves/invers-kryssar-velodrom-v3/` (PR #9, 2026-10-11), built and checked against the
parametric skater. On 2026-10-13, when PR #9 and the STL-skater switch (PR #13) were merged, the move was rebuilt
against the STL skater's contact footprints and the build stopped:

    meet 'lw_push': the puck never reaches W-LW's point [17.12, 31.25] between 0.9115 and 1.5000 s

The meet points (`meets` in the move file) are positions on the parametric blade, and the STL skater is larger (its blade
reaches about 4 mm further), so the left wing's push no longer finds the puck. The move needs its meet points and tunes
redone for the STL skater. Until then it has no saved trace, so the encyclopedia tests and Remotion do not treat it as
built. These files are kept as the record of the v3 result (10 of 11 robustness variants) on the old geometry; they are
not valid against today's figures.
