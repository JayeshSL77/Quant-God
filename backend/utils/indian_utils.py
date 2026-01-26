"""
Indian Financial Utilities
Contains helper functions for Indian-specific formatting and context.
"""
from datetime import datetime, time
from typing import Optional

# =============================================================================
# 1. INDIAN NUMBER FORMATTER
# =============================================================================

def format_indian_number(num: float, currency: bool = True, decimals: int = 2) -> str:
    """
    Converts a number to Indian format (Lakhs, Crores).
    
    Examples:
        format_indian_number(25000000) -> "₹2.50 Cr"
        format_indian_number(150000) -> "₹1.50 L"
        format_indian_number(9500) -> "₹9,500"
    """
    if num is None or num == 0:
        return "₹0" if currency else "0"
    
    prefix = "₹" if currency else ""
    abs_num = abs(num)
    sign = "-" if num < 0 else ""
    
    if abs_num >= 1e7:  # Crores (1 Cr = 10 Million)
        return f"{sign}{prefix}{abs_num / 1e7:.{decimals}f} Cr"
    elif abs_num >= 1e5:  # Lakhs (1 L = 100 Thousand)
        return f"{sign}{prefix}{abs_num / 1e5:.{decimals}f} L"
    else:
        # Standard comma formatting for smaller numbers
        return f"{sign}{prefix}{abs_num:,.0f}"


# =============================================================================
# 2. CIRCUIT BREAKER / ASM-GSM STATUS
# =============================================================================

class CircuitStatus:
    NORMAL = "NORMAL"
    UPPER_CIRCUIT = "UPPER_CIRCUIT"
    LOWER_CIRCUIT = "LOWER_CIRCUIT"
    ASM_STAGE_1 = "ASM_STAGE_1"  # Additional Surveillance Measure
    ASM_STAGE_2 = "ASM_STAGE_2"
    GSM_STAGE_1 = "GSM_STAGE_1"  # Graded Surveillance Measure
    GSM_STAGE_2 = "GSM_STAGE_2"
    TRADING_HALTED = "TRADING_HALTED"


def get_circuit_warning(status: str) -> Optional[str]:
    """
    Returns a user-friendly warning message based on circuit status.
    """
    warnings = {
        CircuitStatus.UPPER_CIRCUIT: "⚠️ This stock is at UPPER CIRCUIT. Trading is restricted. Avoid buying at this level.",
        CircuitStatus.LOWER_CIRCUIT: "⚠️ This stock is at LOWER CIRCUIT. Trading is restricted. High selling pressure detected.",
        CircuitStatus.ASM_STAGE_1: "⚠️ This stock is under ASM Stage 1 surveillance. Higher margins apply.",
        CircuitStatus.ASM_STAGE_2: "🔴 This stock is under ASM Stage 2 surveillance. Trade with extreme caution.",
        CircuitStatus.GSM_STAGE_1: "⚠️ This stock is under GSM Stage 1 (Graded Surveillance). Trade only on Fridays.",
        CircuitStatus.GSM_STAGE_2: "🔴 This stock is under GSM Stage 2. Highly risky. Limited trading allowed.",
        CircuitStatus.TRADING_HALTED: "🛑 Trading is HALTED for this stock. No transactions possible.",
    }
    return warnings.get(status, None)


# =============================================================================
# 3. INDIAN TAX LAYER (LTCG / STCG)
# =============================================================================

class IndianTaxCalculator:
    """
    Calculates capital gains tax for Indian equity investments.
    Based on Budget 2024 rules (effective 23rd July 2024).
    """
    
    # Tax Rates (as of Budget 2024)
    LTCG_RATE = 0.125  # 12.5% for gains > ₹1.25 Lakh
    STCG_RATE = 0.20   # 20% for short-term
    LTCG_EXEMPTION = 125000  # ₹1.25 Lakh annual exemption
    
    @classmethod
    def calculate_tax(
        cls,
        buy_price: float,
        sell_price: float,
        quantity: int,
        holding_days: int
    ) -> dict:
        """
        Calculates the tax liability for a stock sale.
        
        Args:
            buy_price: Purchase price per share
            sell_price: Selling price per share
            quantity: Number of shares
            holding_days: Days between buy and sell
        
        Returns:
            dict with: gain, tax_type, tax_rate, tax_amount, net_gain
        """
        total_buy = buy_price * quantity
        total_sell = sell_price * quantity
        gross_gain = total_sell - total_buy
        
        if gross_gain <= 0:
            return {
                "gross_gain": gross_gain,
                "gross_gain_formatted": format_indian_number(gross_gain),
                "tax_type": "NO_TAX (Loss)",
                "tax_rate": 0,
                "tax_amount": 0,
                "tax_amount_formatted": "₹0",
                "net_gain": gross_gain,
                "net_gain_formatted": format_indian_number(gross_gain)
            }
        
        is_long_term = holding_days > 365
        
        if is_long_term:
            # LTCG: 12.5% on gains above ₹1.25 Lakh
            taxable_gain = max(0, gross_gain - cls.LTCG_EXEMPTION)
            tax_amount = taxable_gain * cls.LTCG_RATE
            tax_type = "LTCG (Long Term)"
            tax_rate = cls.LTCG_RATE
        else:
            # STCG: 20% on all gains
            tax_amount = gross_gain * cls.STCG_RATE
            tax_type = "STCG (Short Term)"
            tax_rate = cls.STCG_RATE
        
        net_gain = gross_gain - tax_amount
        
        return {
            "gross_gain": gross_gain,
            "gross_gain_formatted": format_indian_number(gross_gain),
            "tax_type": tax_type,
            "tax_rate": f"{tax_rate * 100}%",
            "tax_amount": tax_amount,
            "tax_amount_formatted": format_indian_number(tax_amount),
            "net_gain": net_gain,
            "net_gain_formatted": format_indian_number(net_gain),
            "holding_period": "Long Term (>1 year)" if is_long_term else "Short Term (≤1 year)"
        }

    @classmethod
    def get_tax_context_prompt(cls) -> str:
        """
        Returns a prompt snippet for IndicFinGPT to understand Indian tax rules.
        """
        return f"""
        INDIAN CAPITAL GAINS TAX RULES (Budget 2024):
        - LTCG (Long Term Capital Gains): Applies if equity held > 1 year.
          - Tax Rate: {cls.LTCG_RATE * 100}% on gains exceeding ₹{cls.LTCG_EXEMPTION / 100000:.2f} Lakh per year.
        - STCG (Short Term Capital Gains): Applies if equity held ≤ 1 year.
          - Tax Rate: {cls.STCG_RATE * 100}% on all gains.
        - Securities Transaction Tax (STT) is already paid at time of sale.
        
        When advising on selling stocks, always mention the tax impact.
        """


# =============================================================================
# 4. MARKET HOURS AWARENESS
# =============================================================================

def is_indian_market_open() -> dict:
    """
    Checks if Indian stock market (NSE/BSE) is currently open.
    Market Hours: 9:15 AM - 3:30 PM IST, Monday-Friday.
    """
    now = datetime.now()
    current_time = now.time()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    market_open = time(9, 15)
    market_close = time(15, 30)
    pre_open_start = time(9, 0)
    pre_open_end = time(9, 15)
    
    is_weekday = weekday < 5
    is_trading_hours = market_open <= current_time <= market_close
    is_pre_open = pre_open_start <= current_time < pre_open_end
    
    if not is_weekday:
        return {"is_open": False, "status": "CLOSED", "message": "Weekend. Market is closed."}
    elif is_pre_open:
        return {"is_open": False, "status": "PRE_OPEN", "message": "Pre-open session in progress (9:00-9:15 AM)."}
    elif is_trading_hours:
        return {"is_open": True, "status": "OPEN", "message": "Market is open for trading."}
    elif current_time < market_open:
        return {"is_open": False, "status": "CLOSED", "message": f"Market opens at 9:15 AM IST."}
    else:
        return {"is_open": False, "status": "CLOSED", "message": "Market closed for the day. Data is as of last close."}


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    # Test Number Formatter
    print("--- Number Formatter ---")
    print(format_indian_number(25000000))  # ₹2.50 Cr
    print(format_indian_number(150000))     # ₹1.50 L
    print(format_indian_number(9500))       # ₹9,500
    
    # Test Tax Calculator
    print("\n--- Tax Calculator ---")
    result = IndianTaxCalculator.calculate_tax(
        buy_price=100, sell_price=150, quantity=1000, holding_days=400
    )
    print(result)
    
    # Test Market Hours
    print("\n--- Market Hours ---")
    print(is_indian_market_open())
