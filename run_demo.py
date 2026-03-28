import time
import sys

def print_separator():
    print("-" * 40)

def type_text(text, delay=0.01):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def main():
    print()
    print_separator()
    print()
    print("[SYSTEM]")
    print("Autonomous Optimization Engine Started")
    print("Mode: FULLY AUTOMATED")
    print("Human Intervention: NOT REQUIRED")
    print()
    print_separator()
    print()
    
    time.sleep(1)
    
    print("[DETECTION]")
    time.sleep(0.5)
    print("Unused SaaS Licenses: 120")
    print("Monthly Waste: ₹30,000")
    print()
    time.sleep(0.5)
    print("Idle Cloud Resources: 10 Instances")
    print("Monthly Waste: ₹40,000")
    print()
    time.sleep(0.5)
    print("Unattached Storage: 15 Disks")
    print("Monthly Waste: ₹30,000")
    print()
    print_separator()
    print()
    
    time.sleep(1)
    
    print("[PLAN]")
    print("Total Optimization Potential: ₹12,00,000/year")
    print("Micro-Transactions Generated: 12")
    print()
    print_separator()
    print()
    
    time.sleep(1)
    
    print("[MICRO-EXECUTION]")
    print()
    print("Autonomous loop started")
    print("No human intervention required")
    print()
    
    transactions = [
        {"action": "Reduce 30 SaaS licenses", "savings": 7500, "risk": "LOW"},
        {"action": "Reduce 30 SaaS licenses", "savings": 7500, "risk": "LOW"},
        {"action": "Reduce 30 SaaS licenses", "savings": 7500, "risk": "LOW"},
        {"action": "Reduce 30 SaaS licenses", "savings": 7500, "risk": "LOW"},
        
        {"action": "Terminate 2 Idle AWS EC2 instances", "savings": 8000, "risk": "MEDIUM"},
        {"action": "Terminate 3 Idle AWS EC2 instances", "savings": 12000, "risk": "MEDIUM"},
        {"action": "Terminate 2 Idle AWS EC2 instances", "savings": 8000, "risk": "MEDIUM"},
        {"action": "Terminate 3 Idle AWS EC2 instances", "savings": 12000, "risk": "MEDIUM"},
        
        {"action": "Delete 4 Unattached Azure Disks", "savings": 8000, "risk": "LOW"},
        {"action": "Delete 4 Unattached Azure Disks", "savings": 8000, "risk": "LOW"},
        {"action": "Delete 4 Unattached Azure Disks", "savings": 8000, "risk": "LOW"},
        {"action": "Delete 3 Unattached Azure Disks", "savings": 6000, "risk": "LOW"}
    ]
    
    cumulative_savings = 0
    
    for i, t in enumerate(transactions, 1):
        time.sleep(0.8)
        type_text("Executing micro-optimization...")
        time.sleep(0.2)
        cumulative_savings += t["savings"]
        print(f"Step {i}:")
        print(f"Action: {t['action']}")
        print(f"Risk Level: {t['risk']}")
        print(f"Savings: ₹{t['savings']:,.0f}/month")
        print("Status: SUCCESS")
        print(f"Cumulative Savings: ₹{cumulative_savings:,.0f}")
        type_text("Savings updated")
        print()
        
    time.sleep(1)
    print_separator()
    print()
    
    print("[FINAL IMPACT]")
    print()
    print(f"Total Micro-Actions Executed: {len(transactions)}")
    print(f"Monthly Savings: ₹{cumulative_savings:,.0f}")
    print(f"Annual Savings: ₹{cumulative_savings * 12:,.0f}")
    print()
    print("Before Cost: ₹36,00,000/year")
    print(f"After Cost: ₹{3600000 - (cumulative_savings * 12):,.0f}/year")
    print()
    print_separator()
    print()

if __name__ == "__main__":
    main()
