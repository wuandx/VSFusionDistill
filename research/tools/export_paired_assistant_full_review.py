"""Export all named assistant review branches; preserve earlier packages."""
import argparse
import export_paired_reviewed as export
import verify_paired_reviewed as verify
from export_paired_assistant_remaining import REVIEW_ROOTS as PREVIOUS_ROOTS

REVIEW_ROOTS = PREVIOUS_ROOTS + [
    'paired_assistant_mortar_review',
    'paired_assistant_mortar_strong',
    'paired_assistant_mortar_complete_component',
    'paired_assistant_mortar_head_extent',
    'paired_assistant_mortar_supplement',
    'paired_assistant_mortar_supplement_head',
    'paired_assistant_mortar_late_review',
    'paired_assistant_mortar_late_strong',
    'paired_assistant_mortar_late_component',
    'paired_assistant_mortar_late_manual',
    'paired_assistant_mortar_late_supplement',
    'paired_assistant_mortar_late_exhaustion',
    'paired_assistant_bomb_remaining_review',
    'paired_assistant_bomb_remaining_strong',
    'paired_assistant_bomb_primary_return',
    'paired_assistant_bomb_visual_revision',
    'paired_assistant_bomb_old_supplement',
    'paired_assistant_bomb_source_supplement',
    'paired_assistant_bomb_floor_untrimmed',
    'paired_assistant_bomb_floor_source',
    'paired_assistant_bomb_edge_revision',
    'paired_assistant_grenade_remaining_review',
    'paired_assistant_grenade_remaining_strong',
    'paired_assistant_grenade_remaining_body',
    'paired_assistant_grenade_remaining_high',
    'paired_assistant_grenade_remaining_padded',
    'paired_assistant_grenade_remaining_supplement',
    'paired_assistant_grenade_remaining_manual',
    'paired_assistant_grenade_remaining_manual_ring',
    'paired_assistant_grenade_remaining_manual_124915',
    'paired_assistant_grenade_complete_ring',
]
CANDIDATE_RELATIVE_FILES = [
    'paired_visible_expansion/candidates.json',
    'paired_assistant_mortar_supplement/candidates.json',
    'paired_assistant_mortar_late_supplement/candidates.json',
    'paired_assistant_mortar_late_exhaustion/candidates.json',
    'paired_assistant_bomb_old_supplement/candidates.json',
    'paired_assistant_bomb_source_supplement/candidates.json',
    'paired_assistant_bomb_floor_source/candidates.json',
    'paired_grenade_remaining_supplement/candidates.json',
]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    export.OUT = export.ROOT / 'DataSet/paired_assistant_full_review/export'
    export.REVIEW_ROOTS = REVIEW_ROOTS
    export.CANDIDATE_FILES = [export.ROOT/'DataSet'/p for p in CANDIDATE_RELATIVE_FILES]
    verify.OUT = export.OUT
    if not args.verify_only:
        export.main()
    verify.main()
