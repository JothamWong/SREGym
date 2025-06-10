#!/usr/bin/env python3
"""
Test cli.py workflow components for TrainTicket F1 without full k8s deployment
"""
import sys
sys.path.append('.')

def test_problem_registry_integration():
    """Test that F1 problem is properly registered for cli.py workflow"""
    print('=== Testing Problem Registry Integration ===')

    try:
        from srearena.conductor.problems.registry import ProblemRegistry
        registry = ProblemRegistry()

        problem_ids = registry.get_problem_ids()
        print(f'✅ Registry has {len(problem_ids)} problems')

        if 'trainticket_f1_async_message_order' in problem_ids:
            print('✅ F1 problem found in registry problem IDs')
        else:
            print('❌ F1 problem NOT found in registry problem IDs')
            return False

        problem_class = registry.get_problem('trainticket_f1_async_message_order')
        if problem_class:
            print(f'✅ F1 problem class retrieved: {problem_class.__name__}')
        else:
            print('❌ F1 problem class not found')
            return False

        return True

    except Exception as e:
        print(f'❌ Registry integration error: {e}')
        return False

def test_conductor_instantiation():
    """Test that Conductor can be instantiated (what cli.py does first)"""
    print('\n=== Testing Conductor Instantiation ===')

    try:
        from srearena.conductor import Conductor
        conductor = Conductor()
        print('✅ Conductor instantiated successfully')

        if hasattr(conductor, 'problems'):
            print('✅ Conductor has problems registry')
        else:
            print('❌ Conductor missing problems registry')
            return False

        problem_ids = conductor.problems.get_problem_ids()
        if 'trainticket_f1_async_message_order' in problem_ids:
            print('✅ F1 problem accessible via conductor.problems')
        else:
            print('❌ F1 problem not accessible via conductor.problems')
            return False

        return True

    except Exception as e:
        print(f'❌ Conductor instantiation error: {e}')
        return False

def test_f1_problem_components():
    """Test F1 problem components work correctly"""
    print('\n=== Testing F1 Problem Components ===')

    try:
        from srearena.conductor.problems.trainticket_f1_async_message_order import TrainTicketF1AsyncMessageOrderProblem

        print('✅ F1 problem class imports successfully')

        import inspect
        methods = [method for method in dir(TrainTicketF1AsyncMessageOrderProblem)
                  if not method.startswith('_')]

        required_methods = ['inject_fault', 'recover_fault', 'start_workload', 'get_results']
        for method in required_methods:
            if method in methods:
                print(f'✅ F1 problem has {method} method')
            else:
                print(f'❌ F1 problem missing {method} method')
                return False

        return True

    except Exception as e:
        print(f'❌ F1 problem components error: {e}')
        return False

def test_fault_injector_structure():
    """Test fault injector structure without k8s calls"""
    print('\n=== Testing Fault Injector Structure ===')

    try:
        from srearena.generators.fault.inject_tt import TrainTicketFaultInjector

        print('✅ TrainTicketFaultInjector imports successfully')

        import inspect
        source = inspect.getsource(TrainTicketFaultInjector)

        if 'subprocess.run' in source:
            print('❌ TrainTicketFaultInjector still has subprocess.run calls')
            return False
        else:
            print('✅ TrainTicketFaultInjector has no subprocess.run calls')

        if 'self.kubectl' in source:
            print('✅ TrainTicketFaultInjector uses self.kubectl')
        else:
            print('❌ TrainTicketFaultInjector missing self.kubectl usage')
            return False

        return True

    except Exception as e:
        print(f'❌ Fault injector structure error: {e}')
        return False

def main():
    """Run all cli.py workflow component tests"""
    print("=== Testing CLI Workflow Components (No K8s) ===")

    tests = [
        test_problem_registry_integration,
        test_conductor_instantiation,
        test_f1_problem_components,
        test_fault_injector_structure
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            print(f"❌ {test.__name__} failed")

    print(f"\n=== CLI Workflow Component Results: {passed}/{total} tests passed ===")

    if passed == total:
        print("🎉 All CLI workflow components ready - cli.py integration validated!")
        return True
    else:
        print("⚠️ Some CLI workflow components failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
