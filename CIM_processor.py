# -*- coding: utf-8 -*-
"""
Created on Thu Mar 19 00:58:31 2026
Simple PDF processing feeding into Claude Haiku API to output analysis of CIM report.
@author: lamorc2

Note: Output formatting was created by Claude Code (print_report function and it's dependent functions')
"""
import anthropic
import pymupdf
import json
import base64
client = anthropic.Anthropic()


def print_report(data):
    # Confidence color coding using ANSI codes
    confidence_colors = {
        "High":   "\033[92m",  # green
        "Medium": "\033[93m",  # yellow
        "Low":    "\033[91m",  # red
    }
    risk_colors = {
        "High":   "\033[91m",  # red
        "Medium": "\033[93m",  # yellow
        "Low":    "\033[92m",  # green
    }
    RESET = "\033[0m"
    BOLD  = "\033[1m"
    DIM   = "\033[2m"

    def val(v):
        return str(v) if v not in (None, "null", "") else f"{DIM}N/A{RESET}"

    def color(value, palette):
        c = palette.get(value, "")
        return f"{c}{BOLD}{value}{RESET}" if c else val(value)

    width = 60
    line  = "─" * width

    print(f"\n{BOLD}{'═' * width}{RESET}")
    print(f"{BOLD}  CIM ANALYSIS REPORT{RESET}")
    print(f"{BOLD}{'═' * width}{RESET}")

    # ── COMPANY OVERVIEW ──────────────────────────────────────
    print(f"\n{BOLD}  COMPANY OVERVIEW{RESET}")
    print(f"  {line}")
    print(f"  {'Company':<25} {val(data.get('company_name'))}")
    print(f"  {'Industry':<25} {val(data.get('industry'))}")
    print(f"  {'Headquarters':<25} {val(data.get('headquarters'))}")
    print(f"  {'Description':<25} {val(data.get('business_description'))}")

    # ── FINANCIALS ────────────────────────────────────────────
    print(f"\n{BOLD}  FINANCIALS{RESET}")
    print(f"  {line}")
    print(f"  {'Revenue (TTM)':<25} {val(data.get('revenue_ttm'))}")
    print(f"  {'EBITDA (TTM)':<25} {val(data.get('ebitda_ttm'))}")
    print(f"  {'EBITDA Margin':<25} {val(data.get('ebitda_margin'))}")
    print(f"  {'Revenue Growth':<25} {val(data.get('revenue_growth_rate'))}")
    print(f"  {'Asking Price':<25} {val(data.get('asking_price'))}")
    print(f"  {'Valuation Multiple':<25} {val(data.get('valuation_multiple'))}")

    # ── QUALITATIVE ───────────────────────────────────────────
    print(f"\n{BOLD}  QUALITATIVE{RESET}")
    print(f"  {line}")
    print(f"  {'Key Customers':<25} {val(data.get('key_customers'))}")

    ccr = data.get('customer_concentration_risk')
    print(f"  {'Concentration Risk':<25} {color(ccr, risk_colors)}")

    print(f"  {'Management Team':<25} {val(data.get('management_team'))}")

    opportunities = data.get('growth_opportunities') or []
    print(f"\n  {BOLD}Growth Opportunities{RESET}")
    for item in opportunities:
        print(f"    {BOLD}+{RESET} {item}")

    risks = data.get('key_risks') or []
    print(f"\n  {BOLD}Key Risks{RESET}")
    for item in risks:
        print(f"    \033[91m-{RESET} {item}")

    # ── META ──────────────────────────────────────────────────
    print(f"\n{BOLD}  META{RESET}")
    print(f"  {line}")
    print(f"  {'Pages Processed':<25} {val(data.get('pages_processed'))}")

    conf = data.get('confidence')
    print(f"  {'Confidence':<25} {color(conf, confidence_colors)}")

    missing = data.get('missing_fields') or []
    if missing:
        print(f"  {'Missing Fields':<25} {', '.join(missing)}")
    else:
        print(f"  {'Missing Fields':<25} {BOLD}\033[92mNone{RESET}")

    print(f"\n{BOLD}{'═' * width}{RESET}\n")


if __name__ == '__main__':
    filename = input("Please input pdf filename:").strip()
    print(filename)
    try:
        pdf = pymupdf.open(filename) 
    except FileNotFoundError:
        print("Error: File not found!")
        exit()
    except pymupdf.EmptyFileError:
        print("ErrorL File is Empty!")
        exit()
    except pymupdf.FileDataError:
        print("File is corrupt or unsupported format")
        exit()
    except RuntimeError as e:
        print(f"Error: {e}")
        exit()
        
        
        
    messages = []
    initial_prompt = """You are a private equity analyst extracting key data from a 
Confidential Information Memorandum (CIM). As I send you pages, read them 
carefully and remember any financial metrics, company info, or risk factors 
you find."""  
    pg_number = 0
    for page in pdf: # iterate the document pages
        pg_number += 1
        print(pg_number)
        text = page.get_text()
        messages.append({
        "role": "user",
        "content": f"Page {pg_number}:\n{text}"
        })
        
    messages.append({
    "role": "user",
    "content": """You've now read the full document. Output a JSON object with 
    these fields: company_name, industry, revenue_ttm, ebitda_ttm, 
    ebitda_margin, revenue_growth_rate, asking_price, business_description, 
    key_risks, missing_fields. Use null for anything you didn't find. Output data in text format exactly matching the following example:
        Target Output:
            # Financials
            # Qualitative
            # Meta
            {
      "company_name": "ABC Corp",
      "industry": "Software/Data Analysis",
      "headquarters": "New York, NY",
      "revenue_ttm": "$42M",          
      "ebitda_ttm": "$8M",
      "ebitda_margin": "19%",
      "revenue_growth_rate": "22% YoY",
      "asking_price": "$210M",
      "valuation_multiple": "~5x revenue / ~26x EBITDA",
      "business_description": "...",
      "key_customers": "...",
      "customer_concentration_risk": "High / Medium / Low",
      "management_team": "...",
      "growth_opportunities": ["..."],
      "key_risks": ["..."],
      "pages_processed": 47,
      "confidence": "High / Medium / Low",  # did Claude find all fields?
      "missing_fields": ["asking_price"],   # what wasn't in the doc
      "pages_for_image_analysis":[0,20,21] #pages that captions imply have figures that could imply insight for missing fields
      }"""
    })
    
#    final_response = client.messages.create(
#    model="claude-haiku-4-5-20251001",
#    max_tokens=4000,
#    system=initial_prompt,
#    messages=messages
#    )
    raw = '```json\n{\n  "company_name": "American Casino and Entertainment Properties LLC (ACEP)",\n  "industry": "Gaming and Entertainment / Hospitality",\n  "headquarters": "Las Vegas, Nevada",\n  "revenue_ttm": "$328.0M (2005 actual); $385.7M (2006E)",\n  "ebitda_ttm": "$89.4M (2005 actual); $86.1M (2006E)",\n  "ebitda_margin": "27.3% (2005); 22.3% (2006E)",\n  "revenue_growth_rate": "7.8% CAGR (2001-2005); 4.9% CAGR projected (2006E-2008E)",\n  "asking_price": null,\n  "valuation_multiple": null,\n  "business_description": "ACEP owns and operates four gaming and entertainment properties in Nevada: (1) Stratosphere Casino Hotel & Tower on the Las Vegas Strip (80,000 sq ft casino, 2,444 rooms, thrill rides), (2) Arizona Charlie\'s Decatur (off-Strip locals casino, 52,000 sq ft, 258 rooms), (3) Arizona Charlie\'s Boulder (off-Strip locals casino, 47,000 sq ft, 303 rooms with RV park), and (4) Aquarius Casino Resort in Laughlin (57,000 sq ft casino, 1,907 rooms - largest hotel in Laughlin). Value-oriented properties emphasizing slot play (80%+ of gaming revenue), quality accommodations, and customer service across tourist and local market segments.",\n  "key_properties": [\n    "Stratosphere Casino Hotel & Tower - Strip property, 1,309 slots, 49 tables, iconic observation tower with thrill rides",\n    "Arizona Charlie\'s Decatur - Locals casino, 1,379 slots, 15 tables, Outback Steakhouse",\n    "Arizona Charlie\'s Boulder - Locals casino, 1,061 slots, 16 tables, 12-acre RV park",\n    "Aquarius Casino Resort - Laughlin property, 1,021 slots, 42 tables, recently acquired from Harrah\'s (May 2006)"\n  ],\n  "key_customers": "Mix of Las Vegas tourists (Stratosphere), local residents within 5-mile radius (Arizona Charlie\'s properties at ~500K people west side, ~423K people east side), Southern California/Arizona visitors and Laughlin locals (Aquarius). A.C.E. Rewards members total ~1.8M across properties.",\n  "customer_concentration_risk": "Low to Medium - diversified across geographic markets (Strip tourists, West Las Vegas locals, Boulder Strip locals, Laughlin), customer segments, and revenue streams (gaming 53.9%, non-gaming 46.1%)",\n  "management_team": "Richard P. Brown (President & CEO, 7 years tenure, ex-Harrah\'s/Hilton), Denise Barton (SVP/CFO, 4 years, ex-KPMG gaming), Ronald P. Lurie (EVP/GM Decatur, 8 years, ex-Las Vegas Mayor), Mark Majetich (SVP/GM Boulder, 6 years, ex-Excalibur/Caesars Tahoe), John Lind (SVP/GM Laughlin, 1 year, ex-Ramada Express). Collective 100+ years gaming industry experience.",\n  "growth_opportunities": [\n    "Stratosphere Strip development - 17 acres undeveloped land + 112,000 sq ft interior space for 1,000-room hotel expansion and/or convention center",\n    "Laughlin market recovery - Aquarius positioned to recapture prominence after $40M capital program; historical EBITDA exceeded $20M; market growing 7.6% (2004) and 4.3% (2005)",\n    "Las Vegas locals market expansion - Clark County population growing 5.5% CAGR vs 1.1% US average; Arizona Charlie\'s properties benefit from demographic tailwinds",\n    "Convention center expansion - Stratosphere 1.3 miles from Las Vegas Convention Center; 22,154 conventions held in 2005 generating $7.6B in attendee spending",\n    "Slot floor optimization - All properties converted to TITO technology; emphasis on 4,700+ slots generating 80%+ of gaming revenue with predictable cash flow"\n  ],\n  "capital_improvements_completed": [\n    "Stratosphere: ~$50M program including 1,444 room renovation, new thrill rides (Insanity, X Scream), TITO conversion, Top of the World restaurant renovation, new Polly Esters nightclub (opening March 2007), wedding chapel redesign, casino floor improvements",\n    "Arizona Charlie\'s Decatur: ~$38M program including 100% TITO conversion, casino floor redesign, Outback Steakhouse addition, A.C.E. Rewards revamp",\n    "Arizona Charlie\'s Boulder: $8.1M casino expansion (June 2006) with 7,300 sq ft new space, 235 new slots, hotel room renovation, TITO conversion",\n    "Aquarius: $40M program (post-May 2006 acquisition) including 1,000 new slot machines, casino floor redesign, re-branding, front lobby renovation, VIP amenities, hotel room refurbishment (continuing through 2008), Starbucks/Outback Steakhouse additions, showroom/lounge renovation"\n  ],\n  "key_risks": [\n    "Construction disruption impact - 2006 capital improvements temporarily disrupted operations and traffic; management believes impact will reverse post-completion",\n    "Las Vegas market softening - Modest market softening in 2006 cited as headwind; uncertainty on duration and severity",\n    "Competition intensity - Red Rock Casino opening (Station Casinos) created pressure on Decatur market; various competitive casinos in Boulder Strip and Laughlin markets",\n    "Laughlin market transition - Aquarius historically strong but weakened due to prior ownership transition, management turnover, lack of maintenance capital; repositioning success not guaranteed",\n    "Execution risk on Aquarius turnaround - Flamingo Laughlin previously underperformed; $40M investment required to recapture $20M+ historical EBITDA levels",\n    "Strip competitive positioning - Stratosphere competes against luxury properties (Wynn, Encore, MGM CityCenter) entering market 2007-2010; relies on \'pricing umbrella\' strategy for value-oriented customers",\n    "Interest rate / leverage risk - $255M in long-term debt (as of 2006E), rising from $215M in 2004; refinancing risk in tightening environment",\n    "Nevada regulatory risk - Gaming operations in Nevada subject to Gaming Commission/Control Board oversight; regulatory changes could impact operations",\n    "Economic sensitivity - Gaming is economically sensitive; 2005-2006 slowdown indicates sector vulnerability to macro cycles",\n    "Capital intensity - Ongoing capital requirements for maintenance and competitive positioning ($46.9M invested in 2006 alone, expected continued investment)"\n  ],\n  "historical_financial_trends": {\n    "revenue_2001_2005": "$242.5M → $250.0M → $262.8M → $300.0M → $328.0M",\n    "ebitda_2001_2005": "$28.1M → $31.3M → $44.1M → $72.4M → $89.4M",\n    "ebitda_margin_expansion": "11.6% (2001) → 27.3% (2005)",\n    "note": "Strong growth 2001-2005 driven by margin expansion and Stratosphere 1,000-room expansion (June 2001); 2006 decline due to capital improvement disruptions"\n  },\n  "projected_financials_2007_2008": {\n    "2006E_PF": "Revenue $429.7M, EBITDA $91.5M, Margin 21.3% (includes Aquarius full-year)",\n    "2007E": "Revenue $450.9M, EBITDA $106.5M, Margin 23.6% (4.9% revenue CAGR, 11.1% EBITDA CAGR)",\n    "2008E": "Revenue $472.8M, EBITDA $112.9M, Margin 23.9%"\n  },\n  "asset_base": {\n    "total_assets_2006E": "$575.8M",\n    "property_equipment_net_2006E": "$445.8M",\n    "total_liabilities_2006E": "$318.1M",\n    "members_equity_2006E": "$257.7M"\n  },\n  "pages_processed": 54,\n  "confidence": "Medium",\n  "missing_fields": [\n    "asking_price / intended valuation",\n    "specific details on AREP parent company structure and support",\n    "detailed competitive win/loss analysis",\n    "customer acquisition cost metrics",\n    "detailed employee count / labor cost structure",\n    "specific debt terms and maturity schedule",\n    "tax structure details beyond consolidated statements"\n  ],\n  "document_metadata": {\n    "document_type": "Confidential Information Memorandum (CIM)",\n    "prepared_by": "Bear, Stearns & Co. Inc.",\n    "issued_date": "February 2007",\n    "financial_advisor": "Bear Stearns (exclusive)",\n    "parent_company": "American Real Estate Partners L.P. (NYSE: ACP)",\n    "process_stage": "Preliminary - Indications of Interest due March 2, 2007",\n    "deal_rationale": "Possible sale of ACEP"\n  }\n}\n```'
 #  raw = final_response.content[0].text
#    print("Raw response:", repr(raw)) 
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.replace("```json", "").replace("```", "").strip() #incase claude wraps the output
        data = json.loads(clean)
    
    if "confidence" in data:
        if data["confidence"] == "High":
            print_report(data)
        else:
            image_test = False
            if data["confidence"] == "Medium" :
                user_input = input("Confidence is Medium, perform image analysis? (Y/N):")
                if user_input == 'Y':
                    image_test = True
            if image_test == True or data["confidence"] == "Low":
                pages = data["pages_for_image_analysis"]
                image_contents = []

                for page in pages:
                    image_list = pdf[page].get_images()
                    if not image_list:
                        continue
                    for img in image_list:
                        xref = img[0]
                        pix = pymupdf.Pixmap(pdf, xref)
                        if pix.n - pix.alpha > 3:  # CMYK → RGB
                            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                        img_b64 = base64.b64encode(pix.tobytes("png")).decode()
                        image_contents.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64
                            }
                        })

                img_prompt = f"""You previously analyzed this CIM document and returned Medium/Low confidence 
                                with these missing fields: {data.get('missing_fields', [])}.

                                I'm now sending you charts, tables, and figures from the pages most likely 
                                to contain this missing information. For each image:
                                - Extract any financial metrics, projections, or data visible in charts or tables
                                - Note any information that fills in the missing fields listed above
                                - Identify any risks or opportunities visible in visual data not captured in text

                                After analyzing all images, return an updated JSON object with the same schema 
                                as before, merging any new findings with what you already know. Only update 
                                fields where the images provide new or more precise information. Use the same 
                                null convention for anything still not found."""
                messages.append({
                    "role": "user",
                    "content": image_contents + [{"type": "text", "text": img_prompt}]
                })
                final_response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=4000,
                    system=initial_prompt,
                    messages=messages
                    )
                raw = final_response.content[0].text
                print("Raw response:", repr(raw)) 
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    clean = raw.replace("```json", "").replace("```", "").strip() #incase claude wraps the output
                    data = json.loads(clean)

                print_report(data)


                            
            
            
        
        
    
        
        

    