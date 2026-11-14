"""Reproduce the named direct-assistant export; existing exports are preserved."""
import argparse
import export_paired_reviewed as export
import verify_paired_reviewed as verify

REVIEW_ROOTS = [
    'paired_local_review', 'paired_local_review_weak',
    'paired_assistant_review', 'paired_assistant_review_broad',
    'paired_assistant_review_arc',
]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    export.OUT = export.ROOT / 'DataSet/paired_assistant_expansion/export'
    export.REVIEW_ROOTS = REVIEW_ROOTS
    verify.OUT = export.OUT
    if not args.verify_only:
        export.main()
    verify.main()
