"""Run routing tests that don't require database"""
import sys
sys.path.insert(0, 'D:\\Edumatrix-Institutional-Academic-and-Placement-Intelligence\\backend')

from test_critical_routing import test_critical_routing

if __name__ == "__main__":
    success = test_critical_routing()
    sys.exit(0 if success else 1)