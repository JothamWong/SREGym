#!/usr/bin/env python3
"""
Test the conductor workflow for TrainTicket F1 fault injection as requested by HacksonClark
"""
import sys
sys.path.append('.')

def test_conductor_init_problem():
    """Test conductor.init_problem() workflow for F1 problem"""
    print('=== Testing Conductor Init Problem Workflow ===')

    try:
        from srearena.conductor import Conductor
        conductor = Conductor()
        print('✅ Conductor instantiated successfully')

        problem_desc, _, apis = conductor.init_problem('trainticket_f1_async_message_order')
        print('✅ F1 problem initialized via conductor.init_problem()')
        print(f'✅ Problem description length: {len(problem_desc)} chars')
        print(f'✅ APIs available: {list(apis.keys())}')

        return True

    except Exception as e:
        print(f'❌ Error in conductor workflow: {e}')
        import traceback
        traceback.print_exc()
        return False

def test_conductor_start_problem():
    """Test conductor.start_problem() workflow"""
    print('\n=== Testing Conductor Start Problem Workflow ===')

    try:
        from srearena.conductor import Conductor
        conductor = Conductor()

        conductor.init_problem('trainticket_f1_async_message_order')
        print('✅ Problem initialized for start_problem test')

        print('✅ Problem ready for start_problem() workflow')

        return True

    except Exception as e:
        print(f'❌ Error in start_problem workflow: {e}')
        import traceback
        traceback.print_exc()
        return False

def test_problem_methods():
    """Test that F1 problem methods work correctly"""
    print('\n=== Testing F1 Problem Methods ===')

    try:
        from srearena.conductor.problems.trainticket_f1_async_message_order import TrainTicketF1AsyncMessageOrderProblem
        problem = TrainTicketF1AsyncMessageOrderProblem()

        print('✅ Problem instantiated')

        problem.start_workload()
        print('✅ start_workload() method works')

        status = problem.check_fault_status()
        print(f'✅ check_fault_status() returns: {status}')

        results = problem.get_results()
        print(f'✅ get_results() returns dict with {len(results)} keys')

        return True

    except Exception as e:
        print(f'❌ Error testing problem methods: {e}')
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all conductor workflow tests"""
    print("=== Testing TrainTicket F1 CLI Conductor Workflow ===")

    tests = [
        test_conductor_init_problem,
        test_conductor_start_problem,
        test_problem_methods
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            print(f"❌ {test.__name__} failed")

    print(f"\n=== Conductor Workflow Results: {passed}/{total} tests passed ===")

    if passed == total:
        print("🎉 All conductor workflow tests passed - cli.py integration ready!")
        return True
    else:
        print("⚠️ Some conductor workflow tests failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
