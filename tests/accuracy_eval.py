"""
Labeled Accuracy Evaluation for AddressGuard AI
--------------------------------------------------
This is NOT a pass/fail unit test suite (see test_pipeline.py / test_auth.py
for that). This is a labeled dataset of realistic addresses, each hand-
annotated with the status a human reviewer would reasonably expect, used to
compute an actual measured accuracy percentage - the honest way to answer
"how accurate is this system", instead of quoting an invented number.

Run:
    python tests/accuracy_eval.py

Each case is a dict:
    text            - the raw input address text
    expected_status - one of VERIFIED / NEEDS CUSTOMER CONFIRMATION /
                       SUSPICIOUS / FAKE ADDRESS

The script runs every case through the real pipeline, compares the actual
final_status to expected_status, and prints per-case results plus an
overall accuracy percentage, broken down by category.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.explainability_service import run_full_pipeline

DATASET = [
    # ---------------- Category A: Complete & valid -> VERIFIED (15) ----------------
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Rahul Sharma, 9876543210, H.No. 2-4-15, Road No. 3, Madhapur, Hyderabad, Telangana, 500081"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Anita Rao, 9123456780, Flat 302, MG Road, Indiranagar, Bengaluru, Karnataka, 560038"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Karthik Iyer, 9445566778, Door No 12, Anna Salai, Anna Nagar, Chennai, Tamil Nadu, 600040"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Neha Verma, 9812345670, House No 45, Ring Road, Rohini, Delhi, Delhi, 110085"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Suresh Patel, 9998887776, Flat 5B, SG Highway, Vastrapur, Ahmedabad, Gujarat, 380015"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Meera Nair, 9744332211, House No 7, MG Road, Kakkanad, Kochi, Kerala, 682030"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Arjun Singh, 9876501234, Plot 21, Civil Lines, Alambagh, Lucknow, Uttar Pradesh, 226005"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Divya Menon, 9900112233, Flat 8C, FC Road, Kothrud, Pune, Maharashtra, 411038"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Ramesh Gupta, 9811223344, House No 19, Park Street, Salt Lake, Kolkata, West Bengal, 700091"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Kavya Reddy, 9666554433, H.No 3-6-12, Road No 2, Kondapur, Hyderabad, Telangana, 500084"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Vikram Rathore, 9887766554, Plot 14, Civil Lines, C-Scheme, Jaipur, Rajasthan, 302001"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Sunita Joshi, 9822334455, Flat 402, Tilak Road, Deccan Gymkhana, Pune, Maharashtra, 411004"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Farhan Khan, 9955443322, House No 88, Station Road, Andheri, Mumbai, Maharashtra, 400058"},
    {"cat": "complete_valid", "expected": "VERIFIED",
     "text": "Deepika Rao, 9633221144, Flat 6A, Residency Road, Jayanagar, Bengaluru, Karnataka, 560011"},

    # ---------------- Category B: One genuinely missing field -> NEEDS CUSTOMER CONFIRMATION (10) ----------------
    {"cat": "missing_house_number", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Rahul Sharma, 9876543210, Road No. 3, Madhapur, Hyderabad, Telangana, 500081"},
    {"cat": "missing_house_number", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Anita Rao, 9123456780, MG Road, Indiranagar, Bengaluru, Karnataka, 560038"},
    {"cat": "missing_street", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Karthik Iyer, 9445566778, Door No 12, Anna Nagar, Chennai, Tamil Nadu, 600040"},
    {"cat": "missing_street", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Neha Verma, 9812345670, House No 45, Rohini, Delhi, Delhi, 110085"},
    {"cat": "missing_locality", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Rahul Sharma, 9876543210, H.No. 2-4-15, Road No. 3, Hyderabad, Telangana, 500081"},
    {"cat": "missing_locality", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Suresh Patel, 9998887776, Flat 5B, SG Highway, Ahmedabad, Gujarat, 380015"},
    {"cat": "missing_pin", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Meera Nair, 9744332211, House No 7, MG Road, Kakkanad, Kochi, Kerala"},
    {"cat": "missing_pin", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Arjun Singh, 9876501234, Plot 21, Civil Lines, Alambagh, Lucknow, Uttar Pradesh"},
    {"cat": "missing_phone", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Divya Menon, Flat 8C, FC Road, Kothrud, Pune, Maharashtra, 411038"},
    {"cat": "missing_phone", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Ramesh Gupta, House No 19, Park Street, Salt Lake, Kolkata, West Bengal, 700091"},

    # ---------------- Category C: Wrong city/state or PIN geographic conflict -> SUSPICIOUS (8) ----------------
    {"cat": "geo_conflict", "expected": "SUSPICIOUS",
     "text": "Ravi Kumar, 9876543210, Flat 5, MG Road, Mumbai, Telangana, 500081"},
    {"cat": "geo_conflict", "expected": "SUSPICIOUS",
     "text": "Sneha Iyer, 9812345678, House No 9, Ring Road, Chennai, Delhi, 600040"},
    {"cat": "geo_conflict", "expected": "SUSPICIOUS",
     "text": "Manoj Verma, 9911223344, Plot 3, Park Street, Kolkata, Gujarat, 700091"},
    {"cat": "geo_conflict", "expected": "SUSPICIOUS",
     "text": "Pooja Shah, 9822113344, Flat 7, SG Highway, Ahmedabad, Kerala, 380015"},
    {"cat": "geo_conflict", "expected": "SUSPICIOUS",
     "text": "Ajay Nair, 9744556677, House No 4, FC Road, Pune, Punjab, 411038"},
    {"cat": "geo_conflict", "expected": "SUSPICIOUS",
     "text": "Rina Das, 9955667788, Flat 2, Tilak Road, Bengaluru, Bihar, 560011"},
    {"cat": "geo_conflict", "expected": "SUSPICIOUS",
     "text": "Sameer Khan, 9633445566, House No 6, Civil Lines, Jaipur, Kerala, 302001"},
    {"cat": "geo_conflict", "expected": "SUSPICIOUS",
     "text": "Latha Menon, 9887654321, Flat 9, Station Road, Kochi, Haryana, 682030"},

    # ---------------- Category D: Invalid / fabricated PIN -> not VERIFIED (7) ----------------
    {"cat": "invalid_pin", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 999999"},
    {"cat": "invalid_pin", "expected": "SUSPICIOUS",
     "text": "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 111111"},
    {"cat": "invalid_pin", "expected": "SUSPICIOUS",
     "text": "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 123456"},
    {"cat": "invalid_phone", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Priya Sharma, 1234567890, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039"},
    {"cat": "invalid_phone", "expected": "SUSPICIOUS",
     "text": "Priya Sharma, 9999999999, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 500039"},
    {"cat": "invalid_pin_and_missing", "expected": "SUSPICIOUS",
     "text": "Priya Sharma, 1234567890, Peerzadiguda, Hyderabad, Telangana, 999999"},
    {"cat": "invalid_pin_short", "expected": "NEEDS CUSTOMER CONFIRMATION",
     "text": "Priya Sharma, 9876543210, H.No 10-101, Road No 1, Peerzadiguda, Hyderabad, Telangana, 12345"},

    # ---------------- Category E: Random / garbage text -> FAKE ADDRESS (5) ----------------
    {"cat": "random_text", "expected": "FAKE ADDRESS", "text": "asdkj qweoiu zxcvb qwer asdf zxcv lkjh gfds"},
    {"cat": "random_text", "expected": "FAKE ADDRESS", "text": "xyzxyz abcabc qweqwe zxczxc"},
    {"cat": "random_text", "expected": "FAKE ADDRESS", "text": "test test test test address address address"},
    {"cat": "random_text", "expected": "FAKE ADDRESS", "text": "asdf"},
    {"cat": "random_text", "expected": "FAKE ADDRESS", "text": "lkjhg mnbvc qazwsx edcrfv tgbyhn"},

    # ---------------- Category F: Format variety, fully complete/valid -> VERIFIED (5) ----------------
    {"cat": "format_labeled", "expected": "VERIFIED",
     "text": "Name: Rahul Sharma\nPhone: 9876543210\nAddress: H.No. 2-4-15, Road No. 3, Madhapur\n"
             "City: Hyderabad\nState: Telangana\nPIN: 500081"},
    {"cat": "format_whatsapp", "expected": "VERIFIED",
     "text": "Deliver to Priya Sharma. Mobile 9876543210. Flat 10-101, Sri Krishna Nagar Colony, "
             "Road No 1, Peerzadiguda, Hyderabad, Telangana 500039."},
    {"cat": "format_paragraph", "expected": "VERIFIED",
     "text": "This is for Anita Rao at 9123456780, staying at Flat 302, MG Road, Indiranagar, "
             "Bengaluru, Karnataka, 560038"},
    {"cat": "format_dash_pin", "expected": "VERIFIED",
     "text": "Rahul Sharma\nH.No. 2-4-15, Road No. 3, Madhapur\nHyderabad, Telangana \u2013 500081\nPhone: 9876543210"},
    {"cat": "format_shuffled_order", "expected": "VERIFIED",
     "text": "500039, Telangana, Hyderabad, Peerzadiguda, Road No 1, H.No 10-101, Priya Sharma, 9876543210"},
]


def run_evaluation():
    results = []
    for case in DATASET:
        r = run_full_pipeline(case["text"])
        actual = r["decision_result"]["final_status"]
        correct = (actual == case["expected"])
        results.append({
            "category": case["cat"],
            "expected": case["expected"],
            "actual": actual,
            "confidence": r["confidence_result"]["score"],
            "correct": correct,
            "text": case["text"][:60].replace("\n", " | "),
        })
    return results


def print_report(results):
    total = len(results)
    correct = sum(1 for r in results if r["correct"])

    print(f"{'CATEGORY':<26}{'EXPECTED':<28}{'ACTUAL':<28}{'CONF':<6}{'OK':<4}TEXT")
    print("-" * 130)
    for r in results:
        mark = "PASS" if r["correct"] else "FAIL"
        print(f"{r['category']:<26}{r['expected']:<28}{r['actual']:<28}{r['confidence']:<6}{mark:<4}{r['text']}")

    print("\n--- By category ---")
    by_cat = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r["correct"])
    for cat, vals in by_cat.items():
        print(f"  {cat:<26} {sum(vals)}/{len(vals)}")

    print("\n" + "=" * 50)
    print(f"OVERALL ACCURACY: {correct}/{total} = {round(correct / total * 100, 1)}%")
    print("=" * 50)


if __name__ == "__main__":
    print_report(run_evaluation())
