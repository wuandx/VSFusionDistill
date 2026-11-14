"""Export the next reviewed tranche without overwriting earlier packages."""
import argparse
import export_paired_reviewed as export
import verify_paired_reviewed as verify
from export_paired_assistant_expansion import REVIEW_ROOTS as PREVIOUS_ROOTS

REVIEW_ROOTS = PREVIOUS_ROOTS + [
    'paired_assistant_remaining_review',
    'paired_assistant_remaining_broad',
    'paired_assistant_remaining_strong',
]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    export.OUT = export.ROOT / 'DataSet/paired_assistant_remaining/export'
    export.REVIEW_ROOTS = REVIEW_ROOTS
    verify.OUT = export.OUT
    if not args.verify_only:
        export.main()
    verify.main()
